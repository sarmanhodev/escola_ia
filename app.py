from datetime import date
from flask import Flask, flash, redirect, render_template, request, url_for, jsonify
from sqlalchemy import func, cast, Integer
from sqlalchemy.exc import SQLAlchemyError
from config import Config
from models import db, Aluno, Turma, Nota, Frequencia, ConversaIA, MensagemIA
from services.ollama_service import perguntar_ia, interpretar_diagnostico_pedagogico
import requests
from functions import *


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


@app.route("/")
def index():
    medias = (
        db.session.query(Nota.aluno_id, func.avg(Nota.valor))
        .group_by(Nota.aluno_id)
        .all()
    )
    return render_template(
        "index.html",
        alunos=Aluno.query.count(),
        turmas=Turma.query.count(),
        notas=Nota.query.count(),
        abaixo=sum(media < 6 for _, media in medias),
    )


@app.route("/alunos")
def alunos():
    return render_template(
        "alunos.html",
        alunos=Aluno.query.order_by(Aluno.nome).all(),
        turmas=Turma.query.order_by(Turma.nome).all(),
        proxima_matricula=gerar_proxima_matricula(),
    )


@app.post("/alunos")
def criar_aluno():
    nome = request.form.get("nome", "").strip()
    matricula = request.form.get("matricula", "").strip()
    turma_id = request.form.get("turma_id", type=int)

    if not nome or not matricula or not db.session.get(Turma, turma_id):
        flash("Preencha corretamente todos os campos.", "danger")

    elif Aluno.query.filter_by(matricula=matricula).first():
        flash("Matrícula já cadastrada.", "danger")

    else:
        db.session.add(Aluno(nome=nome, matricula=matricula, turma_id=turma_id))
        db.session.commit()
        flash("Aluno cadastrado.", "success")
    return redirect(url_for("alunos"))


@app.post("/alunos/<int:id>/editar")
def editar_aluno(id):

    aluno = db.session.get(Aluno, id)

    if not aluno:
        return jsonify({"success": False, "message": "Aluno não encontrado."}), 404

    nome = request.form.get("nome", "").strip()
    turma_id = request.form.get("turma_id", type=int)

    if not nome:
        return jsonify({"success": False, "message": "Informe o nome do aluno."}), 400

    if not turma_id:
        return jsonify({"success": False, "message": "Selecione uma turma."}), 400

    turma = db.session.get(Turma, turma_id)

    if not turma:
        return (
            jsonify({"success": False, "message": "A turma selecionada não existe."}),
            400,
        )

    try:
        aluno.nome = nome
        aluno.turma_id = turma.id

        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Aluno atualizado com sucesso!",
                    "aluno": {
                        "id": aluno.id,
                        "nome": aluno.nome,
                        "matricula": aluno.matricula,
                        "turma_id": turma.id,
                        "turma": turma.nome,
                    },
                }
            ),
            200,
        )

    except SQLAlchemyError:

        db.session.rollback()

        app.logger.exception("Erro ao atualizar aluno %s", id)

        return (
            jsonify(
                {"success": False, "message": "Não foi possível atualizar o aluno."}
            ),
            500,
        )


@app.get("/alunos/<int:id>/dados")
def dados_aluno(id):

    aluno = db.get_or_404(Aluno, id)

    turmas = Turma.query.order_by(Turma.nome.asc()).all()

    return jsonify(
        {
            "success": True,
            "aluno": {
                "id": aluno.id,
                "nome": aluno.nome,
                "matricula": aluno.matricula,
                "turma_id": aluno.turma_id,
            },
            "turmas": [{"id": turma.id, "nome": turma.nome} for turma in turmas],
        }
    )


@app.post("/alunos/<int:id>/excluir")
def excluir_aluno(id):

    aluno = db.session.get(Aluno, id)

    if not aluno:
        return jsonify({"success": False, "message": "Aluno não encontrado."}), 404

    try:
        db.session.delete(aluno)
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Aluno excluído com sucesso!",
                    "idAluno": id,
                }
            ),
            200,
        )

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception("Erro ao excluir aluno %s", id)

        return (
            jsonify({"success": False, "message": "Não foi possível excluir o aluno."}),
            500,
        )


@app.route("/turmas", methods=["GET", "POST"])
def turmas():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        ano = request.form.get("ano_letivo", type=int)
        if not nome or not ano or not 2000 <= ano <= 2100:
            flash("Turma ou ano inválidos.", "danger")
        elif Turma.query.filter_by(nome=nome).first():
            flash("Turma já cadastrada.", "danger")
        else:
            db.session.add(Turma(nome=nome, ano_letivo=ano))
            db.session.commit()
            flash("Turma cadastrada.", "success")
        return redirect(url_for("turmas"))
    return render_template("turmas.html", turmas=Turma.query.order_by(Turma.nome).all())


@app.route("/notas", methods=["GET", "POST"])
def notas():
    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        disciplina = request.form.get("disciplina", "").strip()
        bimestre = request.form.get("bimestre", type=int)
        try:
            valor = float(request.form.get("valor", "").replace(",", "."))
        except ValueError:
            valor = -1
        if (
            not db.session.get(Aluno, aluno_id)
            or not disciplina
            or bimestre not in (1, 2, 3, 4)
            or not 0 <= valor <= 10
        ):
            flash("Dados da nota inválidos.", "danger")
        else:
            nota = Nota.query.filter_by(
                aluno_id=aluno_id, disciplina=disciplina, bimestre=bimestre
            ).first()
            if nota:
                nota.valor = valor
            else:
                db.session.add(
                    Nota(
                        aluno_id=aluno_id,
                        disciplina=disciplina,
                        bimestre=bimestre,
                        valor=valor,
                    )
                )
            db.session.commit()
            flash("Nota salva.", "success")
        return redirect(url_for("notas"))
    return render_template(
        "notas.html",
        alunos=Aluno.query.order_by(Aluno.nome).all(),
        notas=Nota.query.order_by(Nota.id.desc()).all(),
    )


@app.route("/frequencia", methods=["GET", "POST"])
def frequencia():
    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        try:
            dia = date.fromisoformat(request.form.get("data", ""))
        except ValueError:
            dia = None
        if (
            not db.session.get(Aluno, aluno_id)
            or dia is None
            or request.form.get("presente") not in ("0", "1")
        ):
            flash("Dados da frequência inválidos.", "danger")
        else:
            presente = request.form["presente"] == "1"
            item = Frequencia.query.filter_by(aluno_id=aluno_id, data=dia).first()
            if item:
                item.presente = presente
            else:
                db.session.add(
                    Frequencia(aluno_id=aluno_id, data=dia, presente=presente)
                )
            db.session.commit()
            flash("Frequência salva.", "success")
        return redirect(url_for("frequencia"))
    return render_template(
        "frequencia.html",
        alunos=Aluno.query.order_by(Aluno.nome).all(),
        frequencias=Frequencia.query.order_by(Frequencia.data.desc()).all(),
        hoje=date.today().isoformat(),
    )


@app.get("/ia")
def pagina_ia():
    return render_template("chat_ia.html")


@app.post("/api/ia/chat")
def chat_ia():
    pergunta = request.form.get("pergunta", "").strip()
    conversa_id = request.form.get("conversa_id", type=int)

    if not pergunta:
        return jsonify({"success": False, "message": "Informe uma pergunta."}), 400
    if len(pergunta) > 2000:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "A pergunta deve ter no máximo 2000 caracteres.",
                }
            ),
            400,
        )

    try:
        conversa = None
        if conversa_id is not None:
            conversa = db.session.get(ConversaIA, conversa_id)
            if conversa is None:
                return (
                    jsonify({"success": False, "message": "Conversa não encontrada."}),
                    404,
                )

        historico = recuperar_historico_ia(conversa.id) if conversa is not None else []
        consulta_escolar = identificar_consulta_escolar_contextual(
            pergunta=pergunta, historico=historico
        )
        
        app.logger.info(
            "DEBUG ESCOLAIA | Pergunta: %r | Normalizada: %r | Consulta: %r",
            pergunta,
            normalizar_pergunta_escolar(pergunta),
            consulta_escolar
        )

        if consulta_escolar is not None:
            # O relatório estruturado sempre é produzido pelo Python.
            resposta = gerar_resposta_consulta_escolar(consulta_escolar)
            app.logger.info(
                "Consulta escolar processada pelo Flask: %s",
                consulta_escolar.get("tipo"),
            )

            # Só interpreta quando um aluno foi identificado sem ambiguidade.
            if consulta_escolar.get(
                "tipo"
            ) == "diagnostico_aluno" and consulta_escolar.get("aluno_id"):
                dados = obter_dados_diagnostico_individual_ia(
                    consulta_escolar["aluno_id"]
                )
                if dados:
                    try:
                        interpretacao = interpretar_diagnostico_pedagogico(dados)
                        if interpretacao:
                            resposta += (
                                "\n\n### Análise pedagógica assistida por IA\n\n"
                                + interpretacao
                            )
                    except (requests.RequestException, ValueError, KeyError, TypeError):
                        # Ollama indisponível? Mantém o relatório factual, sem perder a consulta.
                        app.logger.exception(
                            "Falha ao interpretar diagnóstico no Ollama"
                        )
                        resposta += (
                            "\n\n*Análise complementar por IA indisponível no momento. "
                            "Os indicadores acima foram calculados pelo sistema.*"
                        )
        else:
            # Política de domínio fechado: perguntas não reconhecidas pelo
            # interpretador escolar NÃO são enviadas ao modelo de linguagem.
            # Isso também cobre assuntos externos e perguntas escolares ainda
            # não suportadas pela camada de consultas.
            resposta = (
                "Sou o assistente do EscolaIA e respondo exclusivamente a "
                "consultas sobre os dados escolares disponíveis no sistema: "
                "alunos, turmas, notas, médias, frequência e diagnósticos "
                "pedagógicos.\n\n"
                "Exemplos: 'Quantos alunos estão cadastrados?', "
                "'Quais alunos têm frequência inferior a 75%?' ou "
                "'Faça uma análise de Conan'."
            )
            app.logger.info("Pergunta fora das consultas escolares suportadas")

        if not isinstance(resposta, str) or not resposta.strip():
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Não foi possível gerar uma resposta válida.",
                    }
                ),
                502,
            )
        resposta = resposta.strip()

        if conversa is None:
            conversa = ConversaIA(titulo=pergunta[:150])
            db.session.add(conversa)
            db.session.flush()

        db.session.add_all(
            [
                MensagemIA(conversa_id=conversa.id, papel="user", conteudo=pergunta),
                MensagemIA(
                    conversa_id=conversa.id, papel="assistant", conteudo=resposta
                ),
            ]
        )
        db.session.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Resposta gerada com sucesso.",
                    "conversa_id": conversa.id,
                    "resposta": resposta,
                }
            ),
            200,
        )

    except requests.RequestException:
        db.session.rollback()
        app.logger.exception("Erro de comunicação com o Ollama")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Não foi possível comunicar com a IA local.",
                }
            ),
            503,
        )
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Erro de acesso ou gravação no SQLite")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Não foi possível acessar ou salvar os dados.",
                }
            ),
            500,
        )
    except Exception:
        db.session.rollback()
        app.logger.exception("Erro inesperado no chat")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Ocorreu um erro ao processar sua pergunta.",
                }
            ),
            500,
        )


@app.get("/api/ia/conversas")
def listar_conversas_ia():

    try:

        conversas = ConversaIA.query.order_by(
            ConversaIA.criada_em.desc(), ConversaIA.id.desc()
        ).all()

        lista_conversas = []

        for conversa in conversas:

            lista_conversas.append(
                {
                    "id": conversa.id,
                    "titulo": conversa.titulo,
                    "criada_em": (
                        conversa.criada_em.strftime("%d/%m/%Y %H:%M")
                        if conversa.criada_em
                        else None
                    ),
                }
            )

        return jsonify({"success": True, "conversas": lista_conversas}), 200

    except Exception:

        app.logger.exception("Erro ao listar conversas da IA")

        return (
            jsonify(
                {"success": False, "message": "Não foi possível carregar as conversas."}
            ),
            500,
        )


@app.get("/api/ia/conversas/<int:conversa_id>")
def obter_conversa_ia(conversa_id):

    try:

        conversa = db.session.get(ConversaIA, conversa_id)

        if conversa is None:

            return (
                jsonify({"success": False, "message": "Conversa não encontrada."}),
                404,
            )

        mensagens = (
            MensagemIA.query.filter_by(conversa_id=conversa.id)
            .order_by(MensagemIA.criada_em.asc(), MensagemIA.id.asc())
            .all()
        )

        lista_mensagens = []

        for mensagem in mensagens:

            lista_mensagens.append(
                {
                    "id": mensagem.id,
                    "papel": mensagem.papel,
                    "conteudo": mensagem.conteudo,
                    "criada_em": (
                        mensagem.criada_em.strftime("%d/%m/%Y %H:%M")
                        if mensagem.criada_em
                        else None
                    ),
                }
            )

        return (
            jsonify(
                {
                    "success": True,
                    "conversa": {"id": conversa.id, "titulo": conversa.titulo},
                    "mensagens": lista_mensagens,
                }
            ),
            200,
        )

    except Exception:

        app.logger.exception("Erro ao recuperar mensagens da conversa")

        return (
            jsonify(
                {"success": False, "message": "Não foi possível recuperar a conversa."}
            ),
            500,
        )


@app.delete("/api/ia/conversas/<int:conversa_id>")
def excluir_conversa_ia(conversa_id):

    try:

        conversa = db.session.get(ConversaIA, conversa_id)

        if conversa is None:

            return (
                jsonify({"success": False, "message": "Conversa não encontrada."}),
                404,
            )

        # Remove as mensagens vinculadas à conversa
        (
            MensagemIA.query.filter_by(conversa_id=conversa.id).delete(
                synchronize_session=False
            )
        )

        # Remove a conversa
        db.session.delete(conversa)

        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Conversa excluída com sucesso.",
                    "conversa_id": conversa_id,
                }
            ),
            200,
        )

    except Exception:

        db.session.rollback()

        app.logger.exception("Erro ao excluir conversa da IA")

        return (
            jsonify(
                {"success": False, "message": "Não foi possível excluir a conversa."}
            ),
            500,
        )


@app.get("/api/ia/resumo-escolar")
def resumo_escolar_ia():

    try:

        resumo = obter_resumo_escolar_ia()

        return jsonify({"success": True, "dados": resumo}), 200

    except Exception:

        app.logger.exception("Erro ao consultar resumo escolar")

        return (
            jsonify(
                {"success": False, "message": "Erro ao consultar dados escolares."}
            ),
            500,
        )


@app.get("/api/ia/distribuicao-alunos")
def distribuicao_alunos_ia():

    try:

        distribuicao = obter_distribuicao_alunos_ia()

        return (
            jsonify(
                {
                    "success": True,
                    "total_turmas": len(distribuicao),
                    "distribuicao": distribuicao,
                }
            ),
            200,
        )

    except Exception:

        app.logger.exception("Erro ao consultar distribuição de alunos")

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Erro ao consultar distribuição de alunos.",
                }
            ),
            500,
        )


@app.get("/api/ia/medias-turmas")
def medias_turmas_ia():

    try:

        medias = obter_medias_turmas_ia()

        return (
            jsonify({"success": True, "total_turmas": len(medias), "medias": medias}),
            200,
        )

    except Exception:

        app.logger.exception("Erro ao consultar médias das turmas")

        return (
            jsonify(
                {"success": False, "message": "Erro ao consultar médias escolares."}
            ),
            500,
        )


@app.get("/api/ia/analisar-frequencia")
def rota_analisar_frequencia_ia():

    try:

        limite = request.args.get("limite", default=75, type=float)

        if limite < 0 or limite > 100:

            return (
                jsonify(
                    {"success": False, "message": "O limite deve estar entre 0 e 100."}
                ),
                400,
            )

        resultado = analisar_frequencia_ia(limite_percentual=limite)

        return jsonify({"success": True, "dados": resultado}), 200

    except Exception:

        app.logger.exception("Erro ao analisar frequência escolar")

        return (
            jsonify(
                {"success": False, "message": "Erro ao analisar frequência escolar."}
            ),
            500,
        )


@app.get("/api/ia/frequencia-alunos")
def frequencia_alunos_ia():

    try:

        frequencias = obter_frequencia_alunos_ia()

        return (
            jsonify(
                {
                    "success": True,
                    "total_alunos": len(frequencias),
                    "frequencias": frequencias,
                }
            ),
            200,
        )

    except Exception:

        app.logger.exception("Erro ao consultar frequência dos alunos")

        return (
            jsonify(
                {"success": False, "message": "Erro ao consultar frequência escolar."}
            ),
            500,
        )


@app.route("/debug/disciplinas")
def debug_disciplinas():
    from sqlalchemy import func
    from models import Nota, db

    resultados = (
        db.session.query(Nota.disciplina, func.count(Nota.id).label("quantidade"))
        .group_by(Nota.disciplina)
        .order_by(Nota.disciplina)
        .all()
    )

    return {
        "disciplinas": [
            {"nome": item.disciplina, "quantidade_notas": item.quantidade}
            for item in resultados
        ]
    }


@app.route("/debug/consulta-notas")
def debug_consulta_notas():
    from functions import identificar_consulta_escolar

    pergunta = "Qual turma possui a maior média em Matemática?"

    consulta = identificar_consulta_escolar(pergunta)

    return {"pergunta": pergunta, "consulta_identificada": consulta}


with app.app_context():
    db.create_all()
    seed()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
