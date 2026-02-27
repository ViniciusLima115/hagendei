import os
import re
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import HORARIO_ABERTURA, HORARIO_FECHAMENTO, INTERVALO_MINUTOS
from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.cliente import Cliente
from app.models.servico import Servico
from app.services.agenda_service import gerar_horarios_disponiveis
from app.services.notificacao_service import (
    agendar_lembretes_agendamento,
    enviar_mensagem_whatsapp,
    montar_mensagem_confirmacao,
)


BOOKING_PUBLIC_BASE_URL = os.getenv("BOOKING_PUBLIC_BASE_URL", "https://app.virtualbarber.shop")


def _normalizar_texto(texto: str) -> str:
    return " ".join((texto or "").strip().lower().split())


def _normalizar_telefone(telefone: str) -> str:
    digits = re.sub(r"\D", "", telefone or "")
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return digits


def _eh_saudacao(texto: str) -> bool:
    return _normalizar_texto(texto) in {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "menu"}


def montar_link_agendamento(slug: str) -> str:
    base = BOOKING_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{slug}"


def montar_mensagem_link_agendamento(nome_barbearia: str, slug: str) -> str:
    return (
        f"Oi. Para agendar na {nome_barbearia}, use este link:\n"
        f"{montar_link_agendamento(slug)}"
    )


def deve_responder_com_link(texto: str) -> bool:
    msg = _normalizar_texto(texto)
    if _eh_saudacao(msg):
        return True
    return len(msg) <= 20


def obter_barbearia_por_slug(db: Session, slug: str) -> Barbearia | None:
    return db.query(Barbearia).filter(Barbearia.slug == slug.strip().lower()).first()


def obter_lookup_publico(
    db: Session,
    *,
    slug: str,
    barbeiro_id: int | None = None,
    servico_id: int | None = None,
    data_referencia: date | None = None,
) -> dict:
    barbearia = obter_barbearia_por_slug(db, slug)
    if not barbearia:
        raise ValueError("Barbearia nao encontrada.")

    barbeiros = (
        db.query(Barbeiro)
        .filter(
            Barbeiro.barbershop_id == barbearia.id,
            Barbeiro.ativo.is_(True),
        )
        .order_by(Barbeiro.id.asc())
        .all()
    )
    servicos = (
        db.query(Servico)
        .filter(Servico.barbearia_id == barbearia.id)
        .order_by(Servico.id.asc())
        .all()
    )

    if not data_referencia:
        data_referencia = datetime.now().date()

    horarios: list[str] = []
    horarios_grade: list[dict[str, str | bool]] = []
    if barbeiro_id and servico_id:
        duracao = None
        barbeiro_escolhido = next((item for item in barbeiros if item.id == barbeiro_id), None)
        servico_escolhido = next((item for item in servicos if item.id == servico_id), None)
        if barbeiro_escolhido and servico_escolhido:
            duracao = _duracao_servico(barbeiro=barbeiro_escolhido, servico=servico_escolhido)

        horarios = gerar_horarios_disponiveis(
            db=db,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
            data=datetime.combine(data_referencia, time(0, 0)),
            tenant_id=barbearia.id,
        )
        if duracao:
            horarios_disponiveis_set = set(horarios)
            horarios_grade = [
                {
                    "hora": slot.strftime("%H:%M"),
                    "disponivel": slot.strftime("%H:%M") in horarios_disponiveis_set,
                }
                for slot in _gerar_grade_horarios(data_referencia, duracao)
            ]

    return {
        "nome": barbearia.nome,
        "slug": barbearia.slug,
        "barbeiros": barbeiros,
        "servicos": servicos,
        "horarios_disponiveis": horarios,
        "horarios_grade": horarios_grade,
    }


def _duracao_servico(
    *,
    barbeiro: Barbeiro,
    servico: Servico,
) -> int:
    mapa = barbeiro.tempo_por_servico if isinstance(barbeiro.tempo_por_servico, dict) else {}
    custom = mapa.get(str(servico.id))
    if isinstance(custom, int) and custom > 0:
        return custom
    return servico.duracao_minutos


def _gerar_grade_horarios(data_referencia: date, duracao_minutos: int) -> list[datetime]:
    inicio = datetime.combine(data_referencia, time(HORARIO_ABERTURA, 0))
    fim = datetime.combine(data_referencia, time(HORARIO_FECHAMENTO, 0))
    grade: list[datetime] = []
    atual = inicio
    while atual + timedelta(minutes=duracao_minutos) <= fim:
        grade.append(atual)
        atual += timedelta(minutes=INTERVALO_MINUTOS)
    return grade


def _buscar_ou_criar_cliente(
    db: Session,
    *,
    tenant_id: int,
    telefone: str,
    nome: str,
) -> Cliente:
    cliente = (
        db.query(Cliente)
        .filter(
            Cliente.telefone == telefone,
            Cliente.barbearia_id == tenant_id,
        )
        .first()
    )
    if cliente:
        if nome and cliente.nome != nome:
            cliente.nome = nome
        return cliente

    cliente = Cliente(
        nome=nome,
        telefone=telefone,
        etapa_atual="menu",
        barbearia_id=tenant_id,
    )
    db.add(cliente)
    db.flush()
    return cliente


def criar_agendamento_publico(
    db: Session,
    *,
    slug: str,
    cliente_nome: str,
    cliente_telefone: str,
    barbeiro_id: int,
    servico_id: int,
    data: date,
    hora_inicio: time,
) -> dict:
    barbearia = obter_barbearia_por_slug(db, slug)
    if not barbearia:
        raise ValueError("Barbearia nao encontrada.")

    barbeiro = (
        db.query(Barbeiro)
        .filter(
            Barbeiro.id == barbeiro_id,
            Barbeiro.barbershop_id == barbearia.id,
            Barbeiro.ativo.is_(True),
        )
        .first()
    )
    if not barbeiro:
        raise ValueError("Barbeiro nao encontrado.")

    servico = (
        db.query(Servico)
        .filter(
            Servico.id == servico_id,
            Servico.barbearia_id == barbearia.id,
        )
        .first()
    )
    if not servico:
        raise ValueError("Servico nao encontrado.")

    inicio = datetime.combine(data, hora_inicio.replace(second=0, microsecond=0))
    if inicio < datetime.now():
        raise ValueError("Horario no passado nao permitido.")

    duracao = _duracao_servico(barbeiro=barbeiro, servico=servico)
    fim = inicio + timedelta(minutes=duracao)

    conflito = (
        db.query(Agendamento)
        .filter(
            Agendamento.barbeiro_id == barbeiro.id,
            Agendamento.barbearia_id == barbearia.id,
            Agendamento.status.in_(["pendente", "confirmado"]),
            Agendamento.data_hora_inicio < fim,
            Agendamento.data_hora_fim > inicio,
        )
        .first()
    )
    if conflito:
        raise ValueError("Horario indisponivel.")

    telefone = _normalizar_telefone(cliente_telefone)
    cliente = _buscar_ou_criar_cliente(
        db,
        tenant_id=barbearia.id,
        telefone=telefone,
        nome=cliente_nome.strip(),
    )

    agendamento = Agendamento(
        tenant_id=barbearia.id,
        cliente_id=cliente.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        barbeiro_id=barbeiro.id,
        servico_id=servico.id,
        data=data,
        hora_inicio=inicio.time(),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        status="confirmado",
    )
    db.add(agendamento)
    db.flush()

    lembretes = agendar_lembretes_agendamento(
        db,
        tenant_id=barbearia.id,
        agendamento_id=agendamento.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        nome_barbearia=barbearia.nome,
        servico_nome=servico.nome,
        inicio=inicio,
    )
    db.commit()
    db.refresh(agendamento)

    mensagem_confirmacao = montar_mensagem_confirmacao(
        nome_barbearia=barbearia.nome,
        cliente_nome=cliente.nome,
        servico_nome=servico.nome,
        inicio=inicio,
    )
    enviar_mensagem_whatsapp(barbearia, cliente.telefone, mensagem_confirmacao)

    return {
        "id": agendamento.id,
        "tenant_id": barbearia.id,
        "slug": barbearia.slug,
        "cliente_nome": agendamento.cliente_nome,
        "cliente_telefone": agendamento.cliente_telefone,
        "barbeiro_id": agendamento.barbeiro_id,
        "servico_id": agendamento.servico_id,
        "data_hora_inicio": agendamento.data_hora_inicio,
        "data_hora_fim": agendamento.data_hora_fim,
        "status": agendamento.status,
        "lembretes_agendados": lembretes,
    }
