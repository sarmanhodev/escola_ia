from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from datetime import datetime, timezone

db = SQLAlchemy()


class Turma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), unique=True, nullable=False)
    ano_letivo = db.Column(db.Integer, nullable=False, default=2026)
    alunos = db.relationship("Aluno", backref="turma", lazy=True)


class Aluno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(30), unique=True, nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    turma_id = db.Column(db.Integer, db.ForeignKey("turma.id"), nullable=False)
    notas = db.relationship("Nota", backref="aluno", cascade="all, delete-orphan")
    frequencias = db.relationship(
        "Frequencia", backref="aluno", cascade="all, delete-orphan"
    )


class Nota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=False)
    disciplina = db.Column(db.String(80), nullable=False)
    bimestre = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    __table_args__ = (UniqueConstraint("aluno_id", "disciplina", "bimestre"),)


class Frequencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=False)
    data = db.Column(db.Date, nullable=False)
    presente = db.Column(db.Boolean, nullable=False)
    __table_args__ = (UniqueConstraint("aluno_id", "data"),)


class ConversaIA(db.Model):
    __tablename__ = "conversas_ia"

    id = db.Column(db.Integer, primary_key=True)

    titulo = db.Column(db.String(150), nullable=False, default="Nova conversa")

    criada_em = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    mensagens = db.relationship(
        "MensagemIA",
        back_populates="conversa",
        cascade="all, delete-orphan",
        order_by="MensagemIA.id",
    )


class MensagemIA(db.Model):
    __tablename__ = "mensagens_ia"

    id = db.Column(db.Integer, primary_key=True)

    conversa_id = db.Column(
        db.Integer, db.ForeignKey("conversas_ia.id"), nullable=False, index=True
    )

    papel = db.Column(db.String(20), nullable=False)

    conteudo = db.Column(db.Text, nullable=False)

    criada_em = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    conversa = db.relationship("ConversaIA", back_populates="mensagens")
