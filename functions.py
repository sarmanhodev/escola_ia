import re

import unicodedata

from datetime import date


from sqlalchemy import Integer, cast, func


from models import Aluno, ConversaIA, Frequencia, MensagemIA, Nota, Turma, db


def recuperar_historico_ia(conversa_id):

    mensagens = (
        MensagemIA.query.filter_by(conversa_id=conversa_id)
        .order_by(MensagemIA.id.desc())
        .limit(20)
        .all()
    )

    mensagens.reverse()

    return [
        {"role": mensagem.papel, "content": mensagem.conteudo} for mensagem in mensagens
    ]


def gerar_proxima_matricula():

    ultima_matricula = db.session.query(
        func.max(cast(Aluno.matricula, Integer))
    ).scalar()

    if ultima_matricula is None:

        return "2026001"

    return str(ultima_matricula + 1)


def seed():

    if Turma.query.first():

        return

    turmas = [Turma(nome="801", ano_letivo=2026), Turma(nome="802", ano_letivo=2026)]

    db.session.add_all(turmas)

    db.session.flush()

    alunos = [
        Aluno(nome="Ana Souza", matricula="2026001", turma_id=turmas[0].id),
        Aluno(nome="Bruno Lima", matricula="2026002", turma_id=turmas[0].id),
        Aluno(nome="Carla Mendes", matricula="2026003", turma_id=turmas[1].id),
    ]

    db.session.add_all(alunos)

    db.session.flush()

    db.session.add_all(
        [
            Nota(aluno_id=alunos[0].id, disciplina="Matemática", bimestre=1, valor=8.0),
            Nota(aluno_id=alunos[1].id, disciplina="Matemática", bimestre=1, valor=5.0),
            Frequencia(aluno_id=alunos[0].id, data=date(2026, 10, 1), presente=True),
            Frequencia(aluno_id=alunos[1].id, data=date(2026, 10, 1), presente=False),
        ]
    )

    db.session.commit()


def obter_resumo_escolar_ia():

    return {
        "total_alunos": db.session.query(func.count(Aluno.id)).scalar() or 0,
        "total_turmas": db.session.query(func.count(Turma.id)).scalar() or 0,
        "distribuicao_turmas": obter_distribuicao_alunos_ia(),
        "medias_turmas": obter_medias_turmas_ia(),
    }


def obter_distribuicao_alunos_ia():

    resultados = (
        db.session.query(
            Turma.id,
            Turma.nome,
            Turma.ano_letivo,
            func.count(Aluno.id).label("total_alunos"),
        )
        .outerjoin(Aluno, Aluno.turma_id == Turma.id)
        .group_by(Turma.id, Turma.nome, Turma.ano_letivo)
        .order_by(Turma.nome.asc())
        .all()
    )

    return [
        {
            "turma_id": turma.id,
            "turma": turma.nome,
            "ano_letivo": turma.ano_letivo,
            "total_alunos": turma.total_alunos,
        }
        for turma in resultados
    ]


def obter_medias_turmas_ia():

    resultados = (
        db.session.query(
            Turma.id.label("turma_id"),
            Turma.nome.label("turma"),
            Turma.ano_letivo,
            func.count(Nota.id).label("total_notas"),
            func.avg(Nota.valor).label("media_notas"),
        )
        .outerjoin(Aluno, Aluno.turma_id == Turma.id)
        .outerjoin(Nota, Nota.aluno_id == Aluno.id)
        .group_by(Turma.id, Turma.nome, Turma.ano_letivo)
        .order_by(Turma.nome.asc())
        .all()
    )

    return [
        {
            "turma_id": item.turma_id,
            "turma": item.turma,
            "ano_letivo": item.ano_letivo,
            "total_notas": item.total_notas,
            "media_notas": (
                round(float(item.media_notas), 2)
                if item.media_notas is not None
                else None
            ),
        }
        for item in resultados
    ]


def obter_frequencia_alunos_ia():

    resultados = (
        db.session.query(
            Aluno.id.label("aluno_id"),
            Aluno.nome.label("aluno"),
            Turma.nome.label("turma"),
            func.count(Frequencia.id).label("total_registros"),
            func.sum(db.case((Frequencia.presente.is_(True), 1), else_=0)).label(
                "total_presencas"
            ),
        )
        .join(Turma, Turma.id == Aluno.turma_id)
        .outerjoin(Frequencia, Frequencia.aluno_id == Aluno.id)
        .group_by(Aluno.id, Aluno.nome, Turma.nome)
        .order_by(Turma.nome.asc(), Aluno.nome.asc())
        .all()
    )

    frequencias = []

    for registro in resultados:

        total = int(registro.total_registros or 0)

        presencas = int(registro.total_presencas or 0)

        frequencias.append(
            {
                "aluno_id": registro.aluno_id,
                "aluno": registro.aluno,
                "turma": registro.turma,
                "total_registros": total,
                "presencas": presencas,
                "faltas": total - presencas,
                "percentual_frequencia": (
                    round(presencas / total * 100, 2) if total else None
                ),
            }
        )

    return frequencias


def analisar_frequencia_ia(limite_percentual=75):

    limite = float(limite_percentual)

    if not 0 <= limite <= 100:

        raise ValueError("O percentual deve estar entre 0 e 100.")

    frequencias = obter_frequencia_alunos_ia()

    encontrados = [
        aluno
        for aluno in frequencias
        if aluno["percentual_frequencia"] is not None
        and aluno["percentual_frequencia"] < limite
    ]

    encontrados.sort(
        key=lambda aluno: (
            aluno["percentual_frequencia"],
            -aluno["faltas"],
            aluno["aluno"],
        )
    )

    return {
        "limite_percentual": limite,
        "total_alunos_analisados": len(frequencias),
        "total_abaixo_limite": len(encontrados),
        "alunos": encontrados,
    }


def gerar_contexto_frequencia_ia(limite_percentual=75):
    """Compatibilidade com integrações que ainda usem contexto resumido."""

    resultado = analisar_frequencia_ia(limite_percentual)

    alunos_exibidos = resultado["alunos"][:15]

    linhas = [
        f"Nome: {aluno['aluno']} | Turma: {aluno['turma']} | "
        f"Frequência: {aluno['percentual_frequencia']}% | "
        f"Faltas: {aluno['faltas']} | Registros: {aluno['total_registros']}"
        for aluno in alunos_exibidos
    ]

    return {
        "tipo": "frequencia_abaixo_limite",
        "limite": resultado["limite_percentual"],
        "total_analisados": resultado["total_alunos_analisados"],
        "total_encontrados": resultado["total_abaixo_limite"],
        "total_exibidos": len(alunos_exibidos),
        "alunos": linhas,
    }


def normalizar_pergunta(texto):

    texto = unicodedata.normalize("NFKD", texto or "")

    return (
        "".join(
            caractere for caractere in texto if not unicodedata.combining(caractere)
        )
        .lower()
        .strip()
    )


def identificar_consulta_frequencia(pergunta):
    """Reconhece apenas consultas simples de frequência abaixo de X%."""

    texto = normalizar_pergunta(pergunta)

    if not re.search(r"\b(frequencia|presenca|assiduidade)\b", texto):

        return None

    if not re.search(
        r"\b(abaixo(?:\s+de)?|inferior\s+a|menor\s+(?:que|do\s+que)|menos\s+de)\b",
        texto,
    ):

        return None

    if re.search(
        r"\b(entre|acima|superior|maior|igual|compar|media|turma\s+com|por\s+turma)\b",
        texto,
    ):

        return None

    percentuais = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*%", texto)

    if len(percentuais) != 1:

        return None

    limite = float(percentuais[0].replace(",", "."))

    return limite if 0 <= limite <= 100 else None


def gerar_resposta_frequencia_ia(limite_percentual):
    """Gera resposta factual sem depender de cálculos do Ollama."""

    resultado = analisar_frequencia_ia(limite_percentual)

    limite = f"{resultado['limite_percentual']:g}"

    total = resultado["total_alunos_analisados"]

    encontrados = resultado["total_abaixo_limite"]

    alunos = resultado["alunos"]

    linhas = [
        f"## Alunos com frequência inferior a {limite}%",
        "",
        f"**Alunos analisados:** {total}",
        f"**Alunos abaixo de {limite}%:** {encontrados}",
        "",
    ]

    if not alunos:

        linhas.append("Nenhum aluno encontrado com esse critério.")

        return "\n".join(linhas)

    linhas.extend(
        [
            "| Aluno | Turma | Frequência | Faltas | Registros |",
            "|---|---|---:|---:|---:|",
        ]
    )

    for aluno in alunos:

        nome = str(aluno["aluno"]).replace("|", "\\\\|").replace("\n", " ")

        turma = str(aluno["turma"]).replace("|", "\\\\|")

        linhas.append(
            f"| {nome} | {turma} | "
            f"{aluno['percentual_frequencia']:.2f}% | "
            f"{aluno['faltas']} | {aluno['total_registros']} |"
        )

    linhas.extend(
        [
            "",
            "**Observação:** os percentuais consideram somente os registros "
            "existentes. Alunos com poucos registros devem ser analisados "
            "com cautela. A frequência isolada não determina reprovação.",
        ]
    )

    return "\n".join(linhas)


def _percentual_pergunta(texto):

    encontrados = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*%", texto)

    if len(encontrados) != 1:

        return None

    valor = float(encontrados[0].replace(",", "."))

    return valor if 0 <= valor <= 100 else None


def _direcao_frequencia(texto):

    abaixo = bool(
        re.search(
            r"\b(abaixo(?:\s+de)?|inferior\s+a|menor\s+(?:que|do\s+que)|menos\s+de)\b",
            texto,
        )
    )

    acima = bool(
        re.search(
            r"\b(acima(?:\s+de)?|superior\s+a|maior\s+(?:que|do\s+que)|mais\s+de)\b",
            texto,
        )
    )

    if abaixo == acima:

        return None

    return "frequencia_abaixo" if abaixo else "frequencia_acima"


def _turma_pergunta(texto):

    achado = re.search(
        r"\bturma\s+(?:(?:de|da|do|numero|n[ºo])\s+)?(\d+[a-z]?)\b", texto
    )

    return achado.group(1) if achado else None


def identificar_consulta_escolar(pergunta):
    """Reconhece consultas completas, sem inferir dados de perguntas ambíguas."""

    texto = normalizar_pergunta(pergunta)

    consulta_individual = identificar_diagnostico_individual_ia(pergunta)
    if consulta_individual is not None:
        return consulta_individual

    consulta_notas = _identificar_consulta_notas(pergunta)
    if consulta_notas is not None:
        return consulta_notas

    percentual = _percentual_pergunta(texto)

    tem_frequencia = bool(re.search(r"\b(frequencia|presenca|assiduidade)\b", texto))

    tem_faltas = bool(re.search(r"\b(falta|faltas|ausencia|ausencias)\b", texto))

    if (
        tem_frequencia
        and percentual is None
        and re.search(r"\b(turma|turmas)\b", texto)
        and re.search(r"\b(media|medias)\b", texto)
        and re.search(r"\b(menor|mais baixa|pior)\b", texto)
    ):

        return {"tipo": "turma_menor_frequencia"}

    if (
        tem_faltas
        and percentual is None
        and re.search(
            r"\b(mais faltas|maior numero de faltas|mais ausencias|maior quantidade de faltas)\b",
            texto,
        )
        and not re.search(r"\b(menos|menor|turma|turmas)\b", texto)
    ):

        return {"tipo": "ranking_faltas", "limite": 10}

    if not tem_frequencia or percentual is None:

        return None

    if re.search(
        r"\b(entre|igual|exatamente|no minimo|no maximo|media|medias|compar)\b", texto
    ):

        return None

    tipo = _direcao_frequencia(texto)

    if tipo is None:

        return None

    consulta = {"tipo": tipo, "limite": percentual}

    turma = _turma_pergunta(texto)

    if turma:

        consulta["turma"] = turma

    return consulta


def _aplicar_continuacao_frequencia(pergunta, consulta_anterior):
    """Atualiza filtros de frequência somente quando a frase é continuação clara."""

    if not consulta_anterior or consulta_anterior.get("tipo") not in (
        "frequencia_abaixo",
        "frequencia_acima",
    ):

        return None

    texto = normalizar_pergunta(pergunta)

    if re.search(r"\b(entre|media|medias|nota|notas|compar|reprov|aprov)\b", texto):

        return None

    percentual = _percentual_pergunta(texto)

    turma = _turma_pergunta(texto)

    direcao = _direcao_frequencia(texto)

    # Não herdar filtros para perguntas que não sinalizam continuação.

    inicio_continuacao = bool(
        re.match(
            r"^(e\b|mas\b|agora\b|somente\b|apenas\b|so\b|da\s+turma\b|na\s+turma\b)",
            texto,
        )
    )

    tem_frequencia = bool(re.search(r"\b(frequencia|presenca|assiduidade)\b", texto))

    if not inicio_continuacao and not tem_frequencia:

        return None

    if percentual is None and turma is None:

        return None

    if percentual is not None and re.search(r"\d+(?:[.,]\d+)?\s*%", texto) is None:

        return None

    if re.search(r"\b(falta|faltas|ausencia|ausencias)\b", texto):

        return None

    nova = dict(consulta_anterior)

    if percentual is not None:

        nova["limite"] = percentual

    if direcao is not None:

        nova["tipo"] = direcao

    if turma is not None:

        nova["turma"] = turma

    return nova


def identificar_consulta_escolar_contextual(pergunta, historico=None):
    """Reconstrói o último contexto estruturado a partir de mensagens do usuário.



    Interrompe a herança ao encontrar uma pergunta não relacionada. Não depende

    de memória global e não mistura contextos entre conversas.

    """

    consulta = identificar_consulta_escolar(pergunta)

    if consulta is not None:

        return consulta

    mensagens = [
        m.get("content", "") for m in (historico or []) if m.get("role") == "user"
    ]

    if not mensagens:

        return None

    # Só aceita continuações curtas/claras, nunca qualquer pergunta genérica.

    texto = normalizar_pergunta(pergunta)

    if not (
        re.match(
            r"^(e\b|mas\b|agora\b|somente\b|apenas\b|so\b|da\s+turma\b|na\s+turma\b)",
            texto,
        )
        or re.search(
            r"\b(frequencia|presenca|assiduidade|nota|notas|media|medias|desempenho)\b",
            texto,
        )
    ):

        return None

    # Reconstrói no máximo as 10 últimas mensagens do usuário.

    contexto = None

    for mensagem in mensagens[-10:]:

        nova = identificar_consulta_escolar(mensagem)

        if nova is not None:

            contexto = nova

        else:

            contexto = _aplicar_continuacao_notas(
                mensagem, contexto
            ) or _aplicar_continuacao_frequencia(mensagem, contexto)

    continuacao_notas = _aplicar_continuacao_notas(pergunta, contexto)
    if continuacao_notas is not None:
        return continuacao_notas
    return _aplicar_continuacao_frequencia(pergunta, contexto)


def _tabela_frequencia_ia(alunos):

    linhas = [
        "| Aluno | Turma | Frequência | Faltas | Registros |",
        "|---|---|---:|---:|---:|",
    ]

    for aluno in alunos:

        nome = str(aluno["aluno"]).replace("|", "\\\\|").replace("\n", " ")

        turma = str(aluno["turma"]).replace("|", "\\\\|")

        percentual = aluno["percentual_frequencia"]

        frequencia = f"{percentual:.2f}%" if percentual is not None else "Sem registros"

        linhas.append(
            f"| {nome} | {turma} | {frequencia} | "
            f"{aluno['faltas']} | {aluno['total_registros']} |"
        )

    return linhas


def gerar_resposta_consulta_escolar(consulta):
    """Monta respostas determinísticas e aplica filtros de turma no Python."""

    tipo = consulta["tipo"]

    if tipo in ("frequencia_abaixo", "frequencia_acima"):

        limite = float(consulta["limite"])

        turma_filtro = consulta.get("turma")

        frequencias = obter_frequencia_alunos_ia()

        if turma_filtro:

            frequencias = [
                a
                for a in frequencias
                if normalizar_pergunta(str(a["turma"]))
                == normalizar_pergunta(str(turma_filtro))
            ]

        if tipo == "frequencia_abaixo":

            alunos = sorted(
                (
                    a
                    for a in frequencias
                    if a["percentual_frequencia"] is not None
                    and a["percentual_frequencia"] < limite
                ),
                key=lambda a: (a["percentual_frequencia"], -a["faltas"], a["aluno"]),
            )

            titulo, rotulo = "inferior", "abaixo"

        else:

            alunos = sorted(
                (
                    a
                    for a in frequencias
                    if a["percentual_frequencia"] is not None
                    and a["percentual_frequencia"] > limite
                ),
                key=lambda a: (
                    -a["percentual_frequencia"],
                    -a["total_registros"],
                    a["aluno"],
                ),
            )

            titulo, rotulo = "superior", "acima"

        sufixo = f" — turma {turma_filtro}" if turma_filtro else ""

        linhas = [
            f"## Alunos com frequência {titulo} a {limite:g}%{sufixo}",
            "",
            f"**Alunos analisados:** {len(frequencias)}",
            "",
            f"**Alunos {rotulo} de {limite:g}%:** {len(alunos)}",
            "",
        ]

        linhas.extend(
            _tabela_frequencia_ia(alunos)
            if alunos
            else ["Nenhum aluno encontrado com esse critério."]
        )

        linhas.extend(
            [
                "",
                "**Observação:** os percentuais usam somente registros de presença existentes. "
                "Alunos com poucos registros exigem cautela; a frequência isolada não determina reprovação.",
            ]
        )

        return "\n".join(linhas)

    if tipo == "diagnostico_aluno":
        return gerar_diagnostico_individual_ia(consulta)

    if tipo.startswith("notas_"):
        return _gerar_resposta_notas(consulta)

    frequencias = obter_frequencia_alunos_ia()

    if tipo == "ranking_faltas":

        alunos = sorted(
            (a for a in frequencias if a["total_registros"] > 0),
            key=lambda a: (-a["faltas"], a["percentual_frequencia"], a["aluno"]),
        )

        limite = consulta.get("limite", 10)

        exibidos = alunos[:limite]

        linhas = [
            "## Alunos com mais faltas",
            "",
            f"**Alunos com registros:** {len(alunos)}",
            "",
            f"**Exibindo:** {len(exibidos)}",
            "",
        ]

        linhas.extend(
            _tabela_frequencia_ia(exibidos)
            if exibidos
            else ["Não há registros de frequência."]
        )

        linhas.extend(
            [
                "",
                "**Observação:** o ranking usa o número absoluto de faltas; "
                "alunos podem ter quantidades diferentes de registros.",
            ]
        )

        return "\n".join(linhas)

    if tipo == "turma_menor_frequencia":

        grupos = {}

        for aluno in frequencias:

            turma = aluno["turma"]

            grupo = grupos.setdefault(
                turma, {"presencas": 0, "registros": 0, "alunos": 0}
            )

            grupo["alunos"] += 1

            grupo["presencas"] += aluno["presencas"]

            grupo["registros"] += aluno["total_registros"]

        validos = [
            (turma, dados) for turma, dados in grupos.items() if dados["registros"] > 0
        ]

        if not validos:

            return "Não há registros de frequência suficientes para comparar as turmas."

        validos.sort(
            key=lambda item: (item[1]["presencas"] / item[1]["registros"], item[0])
        )

        linhas = [
            "## Frequência média por turma",
            "",
            "| Turma | Frequência | Presenças | Registros | Alunos |",
            "|---|---:|---:|---:|---:|",
        ]

        for turma, dados in validos:

            percentual = dados["presencas"] / dados["registros"] * 100

            turma_segura = str(turma).replace("|", "\\\\|")

            linhas.append(
                f"| {turma_segura} | {percentual:.2f}% | "
                f"{dados['presencas']} | {dados['registros']} | {dados['alunos']} |"
            )

        pior = validos[0]

        linhas.extend(
            [
                "",
                f"**Menor frequência:** turma {pior[0]} "
                f"({pior[1]['presencas'] / pior[1]['registros'] * 100:.2f}%).",
                "",
                "**Critério:** total de presenças dividido pelo total de registros da turma "
                "(média ponderada pelos registros, não média simples dos alunos).",
            ]
        )

        return "\n".join(linhas)

    raise ValueError("Tipo de consulta escolar não reconhecido.")


# =============================================================
# EscolaIA — consultas determinísticas de desempenho acadêmico
# Referência: média 6,0; quatro bimestres de peso igual.
# Ausência de notas não é convertida em zero.
# =============================================================

MEDIA_REFERENCIA_IA = 6.0


def obter_desempenho_alunos_ia():
    """Uma média por disciplina e uma média geral por aluno.

    A média geral é a média das médias por disciplina, para não dar
    peso adicional à matéria que tenha mais bimestres lançados.
    """
    alunos = (
        db.session.query(Aluno.id, Aluno.nome, Turma.nome.label("turma"))
        .join(Turma, Turma.id == Aluno.turma_id)
        .order_by(Turma.nome, Aluno.nome)
        .all()
    )
    notas = (
        db.session.query(Nota.aluno_id, Nota.disciplina, Nota.bimestre, Nota.valor)
        .filter(Nota.bimestre.between(1, 4))
        .all()
    )
    agrupadas = {}
    nomes_originais = {}
    for nota in notas:
        disciplina_normalizada = normalizar_pergunta(nota.disciplina).strip()
        chave = (nota.aluno_id, disciplina_normalizada)
        agrupadas.setdefault(chave, []).append(float(nota.valor))
        # Mantém a grafia cadastrada, sem alterar a chave normalizada usada nas consultas.
        nome_atual = nomes_originais.get(disciplina_normalizada)
        nome_novo = str(nota.disciplina).strip()
        if nome_atual is None or (
            sum(c.isalpha() and ord(c) > 127 for c in nome_novo)
            > sum(c.isalpha() and ord(c) > 127 for c in nome_atual)
        ):
            nomes_originais[disciplina_normalizada] = nome_novo

    por_aluno = {}
    for (aluno_id, disciplina), valores in agrupadas.items():
        por_aluno.setdefault(aluno_id, {})[disciplina] = {
            "media": sum(valores) / len(valores),
            "bimestres_registrados": len(valores),
            "nome_exibicao": nomes_originais.get(disciplina, disciplina),
        }

    resultado = []
    for aluno in alunos:
        disciplinas = por_aluno.get(aluno.id, {})
        medias = [item["media"] for item in disciplinas.values()]
        resultado.append(
            {
                "aluno_id": aluno.id,
                "aluno": aluno.nome,
                "turma": aluno.turma,
                "media_geral": sum(medias) / len(medias) if medias else None,
                "disciplinas": disciplinas,
                "total_disciplinas": len(disciplinas),
            }
        )
    return resultado


def _extrair_nota_limite(texto):
    # Ex.: "média inferior a 6", "notas abaixo de 5,5".
    match = re.search(
        r"\b(?:abaixo(?:\s+de)?|inferior\s+a|menor\s+(?:que|do\s+que)|"
        r"acima(?:\s+de)?|superior\s+a|maior\s+(?:que|do\s+que))\s*"
        r"(\d+(?:[.,]\d+)?)\b",
        texto,
    )
    if not match:
        return None
    valor = float(match.group(1).replace(",", "."))
    return valor if 0 <= valor <= 10 else None


def _disciplina_pergunta(texto):
    # Preferir nomes registrados no banco, sem lista fixa de matérias.
    disciplinas = [
        item[0]
        for item in db.session.query(Nota.disciplina).distinct().all()
        if item[0]
    ]
    for disciplina in sorted(disciplinas, key=len, reverse=True):
        nome_normalizado = normalizar_pergunta(disciplina).strip()
        if nome_normalizado and nome_normalizado in texto:
            return disciplina
    return None


def _identificar_consulta_notas(pergunta):
    texto = normalizar_pergunta(pergunta)
    tem_notas = bool(re.search(r"\b(nota|notas|media|medias|desempenho)\b", texto))
    if not tem_notas:
        return None
    if re.search(r"\b(explique|importancia|como funciona|o que e|por que)\b", texto):
        return None
    if re.search(r"\b(entre|igual|exatamente|comparar|compare)\b", texto):
        return None

    disciplina = _disciplina_pergunta(texto)
    turma = _turma_pergunta(texto)
    limite = _extrair_nota_limite(texto)
    direcao = _direcao_frequencia(texto)  # Apenas vocabulário acima/abaixo.
    cruzar = bool(re.search(r"\b(frequencia|presenca|assiduidade)\b", texto))
    percentual = _percentual_pergunta(texto)
    if cruzar and percentual is None:
        return None

    if limite is not None and direcao is not None:
        consulta = {
            "tipo": "notas_abaixo" if direcao == "frequencia_abaixo" else "notas_acima",
            "limite": limite,
        }
    elif re.search(r"\b(turma|turmas)\b", texto) and re.search(
        r"\b(maior|melhor|menor|pior|ranking)\b", texto
    ):
        consulta = {
            "tipo": "notas_turmas",
            "ordem": ("asc" if re.search(r"\b(menor|pior)\b", texto) else "desc"),
        }
    elif re.search(r"\b(maiores|melhores|maior|melhor|ranking|top)\b", texto):
        consulta = {"tipo": "notas_ranking", "ordem": "desc"}
    elif re.search(r"\b(menores|piores|menor|pior)\b", texto):
        consulta = {"tipo": "notas_ranking", "ordem": "asc"}
    else:
        return None

    if disciplina:
        consulta["disciplina"] = disciplina
    if turma:
        consulta["turma"] = turma
    if cruzar:
        if not re.search(r"\b(abaixo|inferior|menor)\b", texto):
            return None
        consulta["frequencia_abaixo"] = percentual
    return consulta


def _aplicar_continuacao_notas(pergunta, consulta_anterior):
    if not consulta_anterior or not consulta_anterior.get("tipo", "").startswith(
        "notas_"
    ):
        return None
    texto = normalizar_pergunta(pergunta)
    if not re.match(
        r"^(e\b|mas\b|agora\b|somente\b|apenas\b|so\b|da\s+turma\b|na\s+turma\b)", texto
    ):
        return None
    if re.search(r"\b(frequencia|presenca|faltas|ausencias|compare|comparar)\b", texto):
        return None
    turma = _turma_pergunta(texto)
    disciplina = _disciplina_pergunta(texto)
    limite = _extrair_nota_limite(texto)
    direcao = _direcao_frequencia(texto)
    if not any((turma, disciplina, limite is not None)):
        return None
    nova = dict(consulta_anterior)
    if turma:
        nova["turma"] = turma
    if disciplina:
        nova["disciplina"] = disciplina
    if limite is not None:
        if nova["tipo"] not in ("notas_abaixo", "notas_acima"):
            return None
        nova["limite"] = limite
    if direcao and nova["tipo"] in ("notas_abaixo", "notas_acima"):
        nova["tipo"] = (
            "notas_abaixo" if direcao == "frequencia_abaixo" else "notas_acima"
        )
    return nova


def _gerar_resposta_notas(consulta):
    tipo = consulta["tipo"]
    turma_filtro = consulta.get("turma")
    disciplina = consulta.get("disciplina")
    alunos = obter_desempenho_alunos_ia()
    if turma_filtro:
        alunos = [
            a
            for a in alunos
            if normalizar_pergunta(a["turma"]) == normalizar_pergunta(turma_filtro)
        ]

    def media(aluno):
        if disciplina:
            # Nomes da disciplina podem conter diferenças de acento,
            # espaços ou capitalização entre registros.
            disciplina_buscada = normalizar_pergunta(disciplina).strip()
            for nome, dados in aluno["disciplinas"].items():
                if normalizar_pergunta(nome).strip() == disciplina_buscada:
                    return dados.get("media")
            return None
        return aluno["media_geral"]

    validos = [a for a in alunos if media(a) is not None]
    escopo = f" em {disciplina}" if disciplina else " geral"
    titulo_turma = f" — turma {turma_filtro}" if turma_filtro else ""
    linhas = []

    if tipo == "notas_turmas":
        grupos = {}
        for aluno in validos:
            grupos.setdefault(aluno["turma"], []).append(media(aluno))
        resultados = [
            (turma, sum(valores) / len(valores), len(valores))
            for turma, valores in grupos.items()
        ]
        resultados.sort(
            key=lambda x: (x[1], x[0]), reverse=consulta.get("ordem") != "asc"
        )
        linhas = [
            f"## Médias por turma{escopo}",
            "",
            "| Turma | Média | Alunos com notas |",
            "|---|---:|---:|",
        ]
        linhas.extend(
            f"| {turma} | {valor:.2f} | {qtd} |" for turma, valor, qtd in resultados
        )
        if not resultados:
            linhas.append(
                "Nenhuma nota encontrada para esse critério. Verifique os nomes das disciplinas cadastradas e os bimestres registrados."
            )
        else:
            linhas.extend(
                [
                    "",
                    f"**Turma em destaque:** {resultados[0][0]} ({resultados[0][1]:.2f}).",
                ]
            )
    else:
        if tipo in ("notas_abaixo", "notas_acima"):
            limite = float(consulta["limite"])
            abaixo = tipo == "notas_abaixo"
            encontrados = [
                a
                for a in validos
                if (media(a) < limite if abaixo else media(a) > limite)
            ]
            descricao = f"{'inferior' if abaixo else 'superior'} a {limite:g}"
            titulo = f"Alunos com média{escopo} {descricao}{titulo_turma}"
            encontrados.sort(
                key=lambda a: (media(a) if abaixo else -media(a), a["aluno"])
            )
        elif tipo == "notas_ranking":
            asc = consulta.get("ordem") == "asc"
            encontrados = sorted(
                validos, key=lambda a: (media(a) if asc else -media(a), a["aluno"])
            )[:10]
            titulo = f"Alunos com {'menores' if asc else 'maiores'} médias{escopo}{titulo_turma}"
        else:
            raise ValueError("Tipo de consulta de notas não reconhecido.")

        linhas = [
            f"## {titulo}",
            "",
            f"**Alunos analisados:** {len(alunos)}",
            f"**Alunos com notas:** {len(validos)}",
            f"**Resultados:** {len(encontrados)}",
            "",
            "| Aluno | Turma | Média | Disciplinas com notas |",
            "|---|---|---:|---:|",
        ]
        for aluno in encontrados:
            nome = str(aluno["aluno"]).replace("|", "\\|").replace("\n", " ")
            linhas.append(
                f"| {nome} | {aluno['turma']} | {media(aluno):.2f} | {aluno['total_disciplinas']} |"
            )
        if not encontrados:
            linhas.append("Nenhum aluno encontrado com esse critério.")
        if tipo == "notas_ranking" and not disciplina:
            linhas.extend(
                [
                    "",
                    "**Atenção:** a média geral pode considerar quantidades diferentes de disciplinas. "
                    "Compare com cautela alunos com histórico incompleto.",
                ]
            )

        if "frequencia_abaixo" in consulta:
            limite_freq = float(consulta["frequencia_abaixo"])
            frequencias = {f["aluno_id"]: f for f in obter_frequencia_alunos_ia()}
            encontrados = [
                a
                for a in encontrados
                if (
                    frequencias.get(a["aluno_id"], {}).get("percentual_frequencia")
                    is not None
                    and frequencias[a["aluno_id"]]["percentual_frequencia"]
                    < limite_freq
                )
            ]
            # Reconstroi tabela e totais após aplicar o cruzamento.
            linhas = [
                f"## Alunos com média{escopo} {descricao} e frequência abaixo de {limite_freq:g}%{titulo_turma}",
                "",
                f"**Alunos analisados:** {len(alunos)}",
                f"**Resultados:** {len(encontrados)}",
                "",
                "| Aluno | Turma | Média | Frequência | Registros de presença |",
                "|---|---|---:|---:|---:|",
            ]
            for aluno in encontrados:
                f = frequencias[aluno["aluno_id"]]
                nome = str(aluno["aluno"]).replace("|", "\\|").replace("\n", " ")
                linhas.append(
                    f"| {nome} | {aluno['turma']} | {media(aluno):.2f} | {f['percentual_frequencia']:.2f}% | {f['total_registros']} |"
                )
            if not encontrados:
                linhas.append("Nenhum aluno encontrado com ambos os critérios.")

    linhas.extend(
        [
            "",
            "**Critério:** média aritmética dos bimestres registrados por disciplina; "
            "média geral calculada entre disciplinas. Notas ausentes não são zero. "
            "A referência 6,0 não determina reprovação automática.",
        ]
    )
    return "\n".join(linhas)


# =============================================================
# EscolaIA — diagnóstico pedagógico individual
# =============================================================


def identificar_diagnostico_individual_ia(pergunta):
    """Identifica alunos por nome completo ou parcial, sem escolher entre homônimos."""
    texto = normalizar_pergunta(pergunta)
    if not re.search(
        r"\b(analise|analisar|diagnostico|situacao escolar|desempenho individual|"
        r"relatorio individual|relatorio pedagogico|como esta o aluno|como esta a aluna)\b",
        texto,
    ):
        return None

    # Remove apenas a formulação do pedido. O restante é o nome pesquisado.
    nome_busca = re.sub(
        r"^(?:faca\s+uma?\s+|gere\s+uma?\s+|quero\s+uma?\s+|"
        r"me\s+mostre\s+uma?\s+)?"
        r"(?:analise|analisar|diagnostico|situacao escolar|desempenho individual|"
        r"relatorio individual|relatorio pedagogico)\s*"
        r"(?:(?:da|do|de|sobre|para)\s+)?"
        r"(?:(?:situacao escolar|desempenho escolar)\s+)?"
        r"(?:(?:da|do|de|sobre|para)\s+)?"
        r"(?:(?:aluna|aluno|estudante)\s+)?"
        r"(?:(?:da|do|de)\s+)?",
        "",
        texto,
    ).strip(" .?!")
    if nome_busca == texto:
        nome_busca = re.sub(r"^como esta (?:o aluno|a aluna)\s+", "", texto).strip(
            " .?!"
        )

    if not nome_busca or nome_busca == texto:
        return {"tipo": "diagnostico_aluno", "aluno_nao_identificado": True}

    alunos = (
        db.session.query(Aluno.id, Aluno.nome, Turma.nome.label("turma"))
        .join(Turma, Turma.id == Aluno.turma_id)
        .all()
    )
    candidatos = [
        {"aluno_id": a.id, "nome": a.nome, "turma": a.turma}
        for a in alunos
        if re.search(
            r"(?<!\w)" + re.escape(nome_busca) + r"(?!\w)", normalizar_pergunta(a.nome)
        )
    ]
    if len(candidatos) == 1:
        return {"tipo": "diagnostico_aluno", "aluno_id": candidatos[0]["aluno_id"]}
    if len(candidatos) > 1:
        return {
            "tipo": "diagnostico_aluno",
            "ambiguidade": sorted(candidatos, key=lambda x: (x["nome"], x["turma"])),
        }
    return {
        "tipo": "diagnostico_aluno",
        "aluno_nao_identificado": True,
        "nome_buscado": nome_busca,
    }


def obter_dados_diagnostico_individual_ia(aluno_id):
    """Retorna dados objetivos, sem texto produzido por IA."""
    aluno = db.session.get(Aluno, aluno_id)
    if aluno is None:
        return None

    desempenho = next(
        (a for a in obter_desempenho_alunos_ia() if a["aluno_id"] == aluno_id), None
    )
    frequencia = next(
        (f for f in obter_frequencia_alunos_ia() if f["aluno_id"] == aluno_id), None
    )
    if desempenho is None:
        return None

    disciplinas = []
    for nome, dados in sorted(desempenho["disciplinas"].items()):
        disciplinas.append(
            {
                "disciplina": dados.get("nome_exibicao", nome),
                "media": round(dados["media"], 2),
                "bimestres_registrados": dados["bimestres_registrados"],
                "abaixo_referencia": dados["media"] < MEDIA_REFERENCIA_IA,
            }
        )

    return {
        "aluno_id": aluno.id,
        "aluno": aluno.nome,
        "matricula": aluno.matricula,
        "turma": aluno.turma.nome,
        "media_geral": (
            round(desempenho["media_geral"], 2)
            if desempenho["media_geral"] is not None
            else None
        ),
        "total_disciplinas": len(disciplinas),
        "disciplinas": disciplinas,
        "frequencia": frequencia,
        "media_referencia": MEDIA_REFERENCIA_IA,
        "referencia_frequencia": 75.0,
    }


def gerar_diagnostico_individual_ia(consulta):
    """Gera relatório factual com indicadores e sugestões não conclusivas."""
    if consulta.get("ambiguidade"):
        candidatos = consulta["ambiguidade"]
        linhas = [
            "Encontrei mais de um aluno correspondente. Escolha pelo nome completo:",
            "",
        ]
        for item in candidatos:
            if isinstance(item, dict):
                linhas.append(f"- **{item['nome']}** — turma {item['turma']}")
            else:
                linhas.append(f"- **{item}**")
        return "\n".join(linhas)
    if consulta.get("aluno_nao_identificado") or not consulta.get("aluno_id"):
        if consulta.get("nome_buscado"):
            return "Não encontrei alunos correspondentes a esse nome. Confira o cadastro ou informe outro nome."
        return "Informe o nome do aluno para gerar o diagnóstico individual."

    dados = obter_dados_diagnostico_individual_ia(consulta["aluno_id"])
    if not dados:
        return "Não foi possível localizar esse aluno no cadastro."

    def seguro(valor):
        return str(valor).replace("|", "\\|").replace("\n", " ")

    linhas = [
        f"## Diagnóstico pedagógico — {seguro(dados['aluno'])}",
        "",
        f"**Turma:** {seguro(dados['turma'])}",
        f"**Matrícula:** {seguro(dados['matricula'])}",
        (
            f"**Média geral:** {dados['media_geral']:.2f}"
            if dados["media_geral"] is not None
            else "**Média geral:** sem notas registradas"
        ),
        "",
        "### Desempenho por disciplina",
        "",
        "| Disciplina | Média | Bimestres registrados | Indicador |",
        "|---|---:|---:|---|",
    ]
    for item in dados["disciplinas"]:
        indicador = "Abaixo de 6,0" if item["abaixo_referencia"] else "6,0 ou superior"
        linhas.append(
            f"| {seguro(item['disciplina'])} | {item['media']:.2f} | "
            f"{item['bimestres_registrados']}/4 | {indicador} |"
        )
    if not dados["disciplinas"]:
        linhas.append("| Nenhuma nota registrada | — | — | Sem dados |")

    f = dados["frequencia"]
    linhas.extend(["", "### Frequência", ""])
    if f and f["percentual_frequencia"] is not None:
        linhas.extend(
            [
                f"**Frequência registrada:** {f['percentual_frequencia']:.2f}%",
                f"**Presenças:** {f['presencas']} · **Faltas:** {f['faltas']} · "
                f"**Registros:** {f['total_registros']}",
            ]
        )
    else:
        linhas.append(
            "Sem registros de frequência suficientes para calcular o percentual."
        )

    linhas.extend(["", "### Pontos de atenção", ""])
    pontos = []
    abaixo = [x["disciplina"] for x in dados["disciplinas"] if x["abaixo_referencia"]]
    if abaixo:
        pontos.append("Médias inferiores a 6,0 em: " + ", ".join(abaixo) + ".")
    if f and f["percentual_frequencia"] is not None and f["percentual_frequencia"] < 75:
        pontos.append(
            "Frequência registrada abaixo da referência de acompanhamento de 75%."
        )
    if f and 0 < f["total_registros"] < 10:
        pontos.append("Poucos registros de frequência: o percentual exige cautela.")
    if any(x["bimestres_registrados"] < 4 for x in dados["disciplinas"]):
        pontos.append(
            "Há disciplinas sem os quatro bimestres registrados; médias parciais."
        )
    if not dados["disciplinas"]:
        pontos.append("Não há notas registradas para avaliação de desempenho.")
    if not pontos:
        pontos.append(
            "Não foram identificados indicadores abaixo das referências adotadas nos dados disponíveis."
        )
    linhas.extend(f"- {p}" for p in pontos)
    linhas.extend(
        [
            "",
            "### Encaminhamentos sugeridos",
            "",
            "Conferir os registros com a equipe pedagógica e, quando necessário, "
            "acompanhar a evolução por disciplina e a assiduidade nas próximas avaliações.",
            "",
            "**Observação:** análise descritiva baseada nos registros existentes. "
            "Não constitui diagnóstico clínico, nem determina aprovação ou reprovação. "
            "A média de referência é 6,0 e o indicador de frequência utilizado é 75%.",
        ]
    )
    return "\n".join(linhas)
