
import argparse
import random

from datetime import date, timedelta

from faker import Faker
from sqlalchemy import func

from app import app
from models import db, Aluno, Turma, Nota, Frequencia


fake = Faker("pt_BR")

ANO_LETIVO = 2026

DISCIPLINAS = [
    "Matemática",
    "Português",
    "História",
    "Geografia",
    "Ciências"
]


def remover_dados_teste():

    # Seleciona somente os alunos gerados
    # pelo script anterior.
    alunos_teste = (
        db.session.query(Aluno.id)
        .filter(Aluno.matricula.like("TESTE-%"))
        .all()
    )

    ids_alunos = [item.id for item in alunos_teste]

    if ids_alunos:

        # Remove os registros dependentes primeiro.
        db.session.query(Nota).filter(
            Nota.aluno_id.in_(ids_alunos)
        ).delete(synchronize_session=False)

        db.session.query(Frequencia).filter(
            Frequencia.aluno_id.in_(ids_alunos)
        ).delete(synchronize_session=False)

        db.session.query(Aluno).filter(
            Aluno.id.in_(ids_alunos)
        ).delete(synchronize_session=False)

    # Remove apenas turmas TESTE- sem alunos.
    turmas_teste = (
        Turma.query
        .filter(Turma.nome.like("TESTE-%"))
        .all()
    )

    total_turmas_removidas = 0

    for turma in turmas_teste:

        possui_alunos = (
            Aluno.query
            .filter_by(turma_id=turma.id)
            .first()
        )

        if possui_alunos is None:

            db.session.delete(turma)
            total_turmas_removidas += 1

    print(f"Alunos de teste removidos: {len(ids_alunos)}")
    print(f"Turmas de teste removidas: {total_turmas_removidas}")


def obter_turmas():

    nomes_turmas = ["801", "802", "803", "804"]

    turmas = []

    for nome in nomes_turmas:

        turma = Turma.query.filter_by(
            nome=nome
        ).first()

        if turma is None:

            turma = Turma(
                nome=nome,
                ano_letivo=ANO_LETIVO
            )

            db.session.add(turma)
            db.session.flush()

        turmas.append(turma)

    return turmas


def gerar_proxima_matricula():

    # Localiza matrículas numéricas do ano letivo.
    # Exemplo: 2026001, 2026002, 2026007.
    prefixo = str(ANO_LETIVO)

    matriculas = (
        db.session.query(Aluno.matricula)
        .filter(Aluno.matricula.like(f"{prefixo}%"))
        .all()
    )

    numeros = []

    for (matricula,) in matriculas:

        if (
            matricula.isdigit()
            and len(matricula) == 7
            and matricula.startswith(prefixo)
        ):

            numeros.append(int(matricula[4:]))

    proximo_numero = max(numeros, default=0) + 1

    if proximo_numero > 999:
        raise ValueError(
            "O limite de matrículas de 7 dígitos "
            "para este ano foi atingido."
        )

    return proximo_numero


def gerar_dias_letivos(qtd_dias):

    datas = []
    dia = date(2026, 2, 2)

    while len(datas) < qtd_dias:

        if dia.weekday() < 5:
            datas.append(dia)

        dia += timedelta(days=1)

    return datas


def popular_banco(qtd_alunos=150, qtd_dias=60):

    with app.app_context():

        try:

            remover_dados_teste()

            turmas = obter_turmas()

            proxima_matricula = gerar_proxima_matricula()

            if proxima_matricula + qtd_alunos - 1 > 999:
                raise ValueError(
                    "A quantidade solicitada ultrapassa "
                    "o limite de matrículas do ano."
                )

            datas = gerar_dias_letivos(qtd_dias)

            for indice in range(qtd_alunos):

                numero_matricula = proxima_matricula + indice

                matricula = (
                    f"{ANO_LETIVO}{numero_matricula:03d}"
                )

                aluno = Aluno(
                    matricula=matricula,
                    nome=fake.name(),
                    turma_id=random.choice(turmas).id
                )

                db.session.add(aluno)
                db.session.flush()

                # Perfis de desempenho fictícios
                perfil = random.choices(
                    ["alto", "medio", "baixo"],
                    weights=[30, 50, 20]
                )[0]

                if perfil == "alto":

                    media_base = 8.5
                    chance_presenca = 0.96

                elif perfil == "medio":

                    media_base = 6.5
                    chance_presenca = 0.85

                else:

                    media_base = 4.0
                    chance_presenca = 0.65

                # Gera notas
                for disciplina in DISCIPLINAS:

                    for bimestre in range(1, 5):

                        valor = round(
                            min(
                                10.0,
                                max(
                                    0.0,
                                    random.gauss(media_base, 1.2)
                                )
                            ),
                            1
                        )

                        db.session.add(
                            Nota(
                                aluno_id=aluno.id,
                                disciplina=disciplina,
                                bimestre=bimestre,
                                valor=valor
                            )
                        )

                # Gera frequências
                for data_aula in datas:

                    db.session.add(
                        Frequencia(
                            aluno_id=aluno.id,
                            data=data_aula,
                            presente=(
                                random.random() < chance_presenca
                            )
                        )
                    )

            db.session.commit()

            print("\nCARGA CONCLUÍDA!")
            print(f"Novos alunos: {qtd_alunos}")
            print(f"Turmas utilizadas: {', '.join(t.nome for t in turmas)}")
            print(f"Notas geradas: {qtd_alunos * 20}")
            print(f"Frequências geradas: {qtd_alunos * len(datas)}")

        except Exception:

            db.session.rollback()
            raise


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--alunos",
        type=int,
        default=150
    )

    parser.add_argument(
        "--dias",
        type=int,
        default=60
    )

    args = parser.parse_args()

    if args.alunos < 1 or args.dias < 1:
        parser.error(
            "Alunos e dias devem ser maiores que zero."
        )

    popular_banco(
        qtd_alunos=args.alunos,
        qtd_dias=args.dias
    )
