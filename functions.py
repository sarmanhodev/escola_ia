"""EscolaIA: consultas escolares determinísticas sobre o banco local.

Compatível com os modelos Aluno, Turma, Nota, Frequencia, MensagemIA e ConversaIA.
Não executa SQL produzido por linguagem natural nem altera dados durante consultas.
"""

import re
import unicodedata
from collections import defaultdict
from datetime import date
from sqlalchemy import Integer, cast, func
from models import Aluno, ConversaIA, Frequencia, MensagemIA, Nota, Turma, db

MEDIA_REFERENCIA_IA = 6.0
FREQUENCIA_REFERENCIA_IA = 75.0
MAX_LINHAS_IA = 50


def normalizar_pergunta(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^\w\s%,.]", " ", texto)
    texto = re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", texto)
    return " ".join(texto.split())


def normalizar_pergunta_escolar(texto):
    return normalizar_pergunta(texto)


def _md(valor):
    return (
        str(valor if valor is not None else "—").replace("|", "\\|").replace("\n", " ")
    )


def _tabela(cabecalhos, linhas, limite=MAX_LINHAS_IA):
    linhas = list(linhas)
    resultado = [
        "| " + " | ".join(cabecalhos) + " |",
        "|" + "|".join("---" for _ in cabecalhos) + "|",
    ]
    resultado.extend(
        "| " + " | ".join(_md(c) for c in linha) + " |" for linha in linhas[:limite]
    )
    if len(linhas) > limite:
        resultado.extend(
            [
                "",
                f"*Exibindo {limite} de {len(linhas)} registros. Refine a consulta para ver um grupo menor.*",
            ]
        )
    return resultado


def recuperar_historico_ia(conversa_id):
    mensagens = (
        MensagemIA.query.filter_by(conversa_id=conversa_id)
        .order_by(MensagemIA.id.desc())
        .limit(20)
        .all()
    )
    return [{"role": m.papel, "content": m.conteudo} for m in reversed(mensagens)]


def gerar_proxima_matricula():
    ultima = db.session.query(func.max(cast(Aluno.matricula, Integer))).scalar()
    return str(int(ultima) + 1) if ultima is not None else "2026001"


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


def obter_distribuicao_alunos_ia():
    registros = (
        db.session.query(
            Turma.id,
            Turma.nome,
            Turma.ano_letivo,
            func.count(Aluno.id).label("total_alunos"),
        )
        .outerjoin(Aluno, Aluno.turma_id == Turma.id)
        .group_by(Turma.id, Turma.nome, Turma.ano_letivo)
        .order_by(Turma.nome, Turma.ano_letivo)
        .all()
    )
    return [
        {
            "turma_id": x.id,
            "turma": x.nome,
            "ano_letivo": x.ano_letivo,
            "total_alunos": x.total_alunos,
        }
        for x in registros
    ]


def obter_medias_turmas_ia():
    registros = (
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
        .order_by(Turma.nome)
        .all()
    )
    return [
        {
            "turma_id": x.turma_id,
            "turma": x.turma,
            "ano_letivo": x.ano_letivo,
            "total_notas": x.total_notas,
            "media_notas": (
                round(float(x.media_notas), 2) if x.media_notas is not None else None
            ),
        }
        for x in registros
    ]


def obter_resumo_escolar_ia():
    return {
        "total_alunos": db.session.query(func.count(Aluno.id)).scalar() or 0,
        "total_turmas": db.session.query(func.count(Turma.id)).scalar() or 0,
        "distribuicao_turmas": obter_distribuicao_alunos_ia(),
        "medias_turmas": obter_medias_turmas_ia(),
    }


def obter_frequencia_alunos_ia():
    registros = (
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
        .order_by(Turma.nome, Aluno.nome)
        .all()
    )
    resultado = []
    for x in registros:
        total, presencas = int(x.total_registros or 0), int(x.total_presencas or 0)
        resultado.append(
            {
                "aluno_id": x.aluno_id,
                "aluno": x.aluno,
                "turma": x.turma,
                "total_registros": total,
                "presencas": presencas,
                "faltas": total - presencas,
                "percentual_frequencia": (
                    round(presencas / total * 100, 2) if total else None
                ),
            }
        )
    return resultado


def analisar_frequencia_ia(limite_percentual=75):
    limite = float(limite_percentual)
    if not 0 <= limite <= 100:
        raise ValueError("O percentual deve estar entre 0 e 100.")
    frequencias = obter_frequencia_alunos_ia()
    alunos = sorted(
        [
            a
            for a in frequencias
            if a["percentual_frequencia"] is not None
            and a["percentual_frequencia"] < limite
        ],
        key=lambda a: (a["percentual_frequencia"], -a["faltas"], a["aluno"]),
    )
    return {
        "limite_percentual": limite,
        "total_alunos_analisados": len(frequencias),
        "total_abaixo_limite": len(alunos),
        "alunos": alunos,
    }


def gerar_contexto_frequencia_ia(limite_percentual=75):
    resultado = analisar_frequencia_ia(limite_percentual)
    exibidos = resultado["alunos"][:15]
    return {
        "tipo": "frequencia_abaixo_limite",
        "limite": resultado["limite_percentual"],
        "total_analisados": resultado["total_alunos_analisados"],
        "total_encontrados": resultado["total_abaixo_limite"],
        "total_exibidos": len(exibidos),
        "alunos": [
            f"Nome: {a['aluno']} | Turma: {a['turma']} | Frequência: {a['percentual_frequencia']}% | Faltas: {a['faltas']} | Registros: {a['total_registros']}"
            for a in exibidos
        ],
    }


def _tabela_frequencia_ia(alunos):
    return _tabela(
        ["Aluno", "Turma", "Frequência", "Presenças", "Faltas", "Registros"],
        [
            (
                a["aluno"],
                a["turma"],
                (
                    f"{a['percentual_frequencia']:.2f}%"
                    if a["percentual_frequencia"] is not None
                    else "Sem registros"
                ),
                a["presencas"],
                a["faltas"],
                a["total_registros"],
            )
            for a in alunos
        ],
    )


def identificar_consulta_frequencia(pergunta):
    consulta = identificar_consulta_escolar(pergunta)
    return (
        consulta.get("limite")
        if consulta and consulta["tipo"] == "frequencia_abaixo"
        else None
    )


def gerar_resposta_frequencia_ia(limite_percentual):
    return gerar_resposta_consulta_escolar(
        {"tipo": "frequencia_abaixo", "limite": limite_percentual}
    )


def obter_desempenho_alunos_ia():
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
    agrupadas = defaultdict(list)
    nomes = {}
    for n in notas:
        chave = normalizar_pergunta(n.disciplina)
        agrupadas[(n.aluno_id, chave)].append(float(n.valor))
        nomes[chave] = str(n.disciplina)
    por_aluno = defaultdict(dict)
    for (aluno_id, disciplina), valores in agrupadas.items():
        por_aluno[aluno_id][disciplina] = {
            "media": sum(valores) / len(valores),
            "bimestres_registrados": len(valores),
            "nome_exibicao": nomes[disciplina],
        }
    resultado = []
    for a in alunos:
        disciplinas = por_aluno.get(a.id, {})
        medias = [d["media"] for d in disciplinas.values()]
        resultado.append(
            {
                "aluno_id": a.id,
                "aluno": a.nome,
                "turma": a.turma,
                "media_geral": sum(medias) / len(medias) if medias else None,
                "disciplinas": disciplinas,
                "total_disciplinas": len(disciplinas),
            }
        )
    return resultado


def _turma_pergunta(texto):
    m = re.search(r"\bturma\s+(?:(?:de|da|do|numero|n)\s+)?(\d+[a-z]?)\b", texto)
    return m.group(1) if m else None


def _turmas_pergunta(texto):
    """Extrai enumerações de turmas, aceitando vírgulas e conjunções."""
    encontrados = []
    for match in re.finditer(
        r"\bturmas?\s+(?:(?:de|da|do|numero|n)\s+)?(\d+[a-z]?)\b", texto
    ):
        encontrados.append(match.group(1))
        resto = texto[match.end() :]
        while True:
            seguinte = re.match(
                r"^\s*(?:(?:e|ou)\s+)?(?:(?:(?:da|na)\s+)?turma\s+)?(\d{3}[a-z]?)\b",
                resto,
            )
            if not seguinte:
                break
            encontrados.append(seguinte.group(1))
            resto = resto[seguinte.end() :]
    return list(dict.fromkeys(encontrados))


def _percentual_pergunta(texto):
    valores = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*%", texto)
    if len(valores) != 1:
        return None
    valor = float(valores[0].replace(",", "."))
    return valor if 0 <= valor <= 100 else None


def _direcao_frequencia(texto):
    abaixo = bool(re.search(r"\b(abaixo|inferior|menor|menos|ate|no maximo)\b", texto))
    acima = bool(
        re.search(r"\b(acima|superior|maior|mais|pelo menos|no minimo)\b", texto)
    )
    if abaixo == acima:
        return None
    return "frequencia_abaixo" if abaixo else "frequencia_acima"


def _extrair_nota_limite(texto):
    """Aceita notas 0-10 e percentuais 0-100, convertendo % para escala 0-10."""
    m = re.search(
        r"\b(?:abaixo(?: de)?|inferior a|menor (?:que|do que)|acima(?: de)?|superior a|maior (?:que|do que))\s+(\d+(?:[.,]\d+)?)\s*(%)?",
        texto,
    )
    if not m:
        return None
    valor = float(m.group(1).replace(",", "."))
    if m.group(2):
        return valor / 10 if 0 <= valor <= 100 else None
    return valor if 0 <= valor <= 10 else None


def _disciplinas_pergunta(texto):
    """Retorna todas as disciplinas mencionadas, sem duplicatas normalizadas."""
    disciplinas = [
        d for (d,) in db.session.query(Nota.disciplina).distinct().all() if d
    ]
    encontradas = {}
    for d in sorted(disciplinas, key=len, reverse=True):
        chave = normalizar_pergunta(d)
        if re.search(r"(?<!\w)" + re.escape(chave) + r"(?!\w)", texto):
            encontradas.setdefault(chave, d)
    return list(encontradas.values())


def _disciplina_pergunta(texto):
    disciplinas = _disciplinas_pergunta(texto)
    return disciplinas[0] if disciplinas else None


def _resolver_aluno(nome):
    busca = normalizar_pergunta(nome)
    if not busca:
        return {"aluno_nao_identificado": True}
    candidatos = []
    for aluno in Aluno.query.all():
        nome_norm = normalizar_pergunta(aluno.nome)
        matricula = normalizar_pergunta(aluno.matricula)
        if busca == matricula or re.search(
            r"(?<!\w)" + re.escape(busca) + r"(?!\w)", nome_norm
        ):
            candidatos.append(aluno)
    if len(candidatos) == 1:
        return {"aluno_id": candidatos[0].id}
    if len(candidatos) > 1:
        return {
            "ambiguidade": [{"nome": a.nome, "turma": a.turma.nome} for a in candidatos]
        }
    return {"aluno_nao_identificado": True, "nome_buscado": nome}


def _aluno_na_pergunta(texto):
    # Busca pelo nome completo ou pelo maior trecho cadastrado; evita tratar 'alunos' como nome.
    candidatos = []
    for aluno in Aluno.query.all():
        nome = normalizar_pergunta(aluno.nome)
        partes = nome.split()
        alternativas = [nome]
        if partes:
            alternativas.append(" ".join(partes[:2]) if len(partes) > 1 else partes[0])
        for termo in alternativas:
            if len(termo) >= 3 and re.search(
                r"(?<!\w)" + re.escape(termo) + r"(?!\w)", texto
            ):
                candidatos.append((len(termo), aluno))
                break
    if not candidatos:
        return None
    maior = max(tamanho for tamanho, _ in candidatos)
    encontrados = [a for tamanho, a in candidatos if tamanho == maior]
    if len(encontrados) == 1:
        return {"aluno_id": encontrados[0].id}
    return {
        "ambiguidade": [{"nome": a.nome, "turma": a.turma.nome} for a in encontrados]
    }


def identificar_diagnostico_individual_ia(pergunta):
    texto = normalizar_pergunta(pergunta)
    if not re.search(
        r"\b(analise|analisar|diagnostico|situacao escolar|desempenho individual|relatorio individual|relatorio pedagogico|como esta)\b",
        texto,
    ):
        return None
    nome = re.sub(
        r"^(?:faca|faz|gere|gerar|quero|mostre|me mostre|preciso de)?\s*(?:uma?|o)?\s*"
        r"(?:analise|analisar|diagnostico|situacao escolar|desempenho individual|relatorio individual|relatorio pedagogico|como esta)\s*"
        r"(?:(?:pedagogica|escolar|individual)\s*)?(?:(?:sobre|da|do|de|para|o|a|aluno|aluna)\s*)*",
        "",
        texto,
    ).strip()
    dados = _resolver_aluno(nome)
    return {"tipo": "diagnostico_aluno", **dados}


def _identificar_consulta_total_alunos(pergunta):
    texto = normalizar_pergunta(pergunta)
    if _turma_pergunta(texto) or re.search(
        r"\b(nota|notas|media|frequencia|faltas|disciplina|bimestre)\b", texto
    ):
        return None
    if re.fullmatch(
        r"(?:quantos|qual (?:e )?(?:o total|a quantidade|o numero) de|total de|quantidade de|numero de)\s+(?:alunos|estudantes)(?:\s+(?:temos|tem|existem|ha|estao cadastrados|estao matriculados|cadastrados|matriculados|na escola|no sistema))?",
        texto,
    ) or re.fullmatch(
        r"(?:total|quantidade|numero) de alunos(?: cadastrados| matriculados)?", texto
    ):
        return {"tipo": "total_alunos"}
    return None


def _identificar_consulta_notas(pergunta):
    texto = normalizar_pergunta(pergunta)
    if not re.search(
        r"\b(nota|notas|media|medias|desempenho|disciplina|disciplinas|bimestre|bimestres)\b",
        texto,
    ):
        return None
    if re.search(r"\b(como funciona|o que e|explique|por que|importancia)\b", texto):
        return None
    turma = _turma_pergunta(texto)
    disciplinas = _disciplinas_pergunta(texto)
    disciplina = disciplinas[0] if len(disciplinas) == 1 else None
    aluno = _aluno_na_pergunta(texto)
    bimestre = re.search(
        r"\b([1-4])\s*(?:o|º)?\s*bimestre\b|\bbimestre\s*([1-4])\b", texto
    )
    bimestre = int(next(x for x in bimestre.groups() if x)) if bimestre else None
    limite = _extrair_nota_limite(texto)
    direcao = _direcao_frequencia(texto)
    consulta = {"tipo": "notas_resumo"}
    if (
        re.search(
            r"\bmedia(?:s)?\s+(?:geral|global)\b|\bqual\s+(?:e\s+)?a\s+media\b", texto
        )
        and not aluno
        and not re.search(r"\b(alunos|estudantes)\b", texto)
    ):
        consulta["tipo"] = "notas_media_geral"
    elif re.search(
        r"\b(quantas|quantos|total|quantidade|numero)\b", texto
    ) and re.search(r"\b(notas|lancamentos|avaliacoes)\b", texto):
        consulta["tipo"] = "notas_total"
    elif limite is not None and direcao:
        consulta.update(
            tipo="notas_abaixo" if direcao == "frequencia_abaixo" else "notas_acima",
            limite=limite,
        )
    elif re.search(
        r"\b(melhor|melhores|maior|maiores|pior|piores|menor|menores|ranking|top)\b",
        texto,
    ):
        asc = bool(re.search(r"\b(pior|piores|menor|menores)\b", texto))
        if re.search(r"\bturmas?\b", texto) and not turma:
            consulta.update(tipo="notas_turmas", ordem="asc" if asc else "desc")
        else:
            consulta.update(tipo="notas_ranking", ordem="asc" if asc else "desc")
    elif aluno:
        consulta["tipo"] = "notas_aluno"
    elif re.search(r"\b(sem nota|sem notas|nao tem nota|nao possuem notas)\b", texto):
        consulta["tipo"] = "notas_sem_registro"
    elif re.search(r"\b(media|medias|desempenho)\b", texto):
        consulta["tipo"] = "notas_resumo"
    elif re.search(r"\b(notas|disciplina|disciplinas|bimestre|bimestres)\b", texto):
        consulta["tipo"] = "notas_listagem"
    if turma:
        consulta["turma"] = turma
    if disciplina:
        consulta["disciplina"] = disciplina
    elif len(disciplinas) > 1:
        consulta["disciplinas"] = disciplinas
    if bimestre:
        consulta["bimestre"] = bimestre
    if aluno:
        consulta.update(aluno)
    percentual = _percentual_pergunta(texto)
    if (
        percentual is not None
        and re.search(r"\b(frequencia|presenca|assiduidade)\b", texto)
        and re.search(r"\b(abaixo|inferior|menor)\b", texto)
    ):
        consulta["frequencia_abaixo"] = percentual
    return consulta


def _consulta_disciplinas(pergunta):
    """Intenções de catálogo e vínculo inferido dos lançamentos de notas."""
    texto = normalizar_pergunta(pergunta)
    menciona_disciplina = bool(
        re.search(r"\b(disciplina|disciplinas|materia|materias)\b", texto)
    )
    disciplinas = _disciplinas_pergunta(texto)
    disciplina = disciplinas[0] if disciplinas else None
    # 'matemática' isolada é ambígua; exigir contexto de consulta.
    vinculo = bool(
        re.search(
            r"\b(cursam|cursa|estudam|estuda|fazem|faz|matriculados em|alunos de|alunos da|estudantes de)\b",
            texto,
        )
    )
    aluno_termo = bool(
        re.search(r"\b(alunos|aluno|estudantes|estudante|matriculados)\b", texto)
    )
    contagem = bool(
        re.search(r"\b(total|quantos|quantas|quantidade|numero|contagem)\b", texto)
    )
    listagem = bool(
        re.search(r"\b(quais|quem|liste|listar|lista|mostre|relacao|nomes)\b", texto)
    )
    turma = _turma_pergunta(texto)
    turmas = _turmas_pergunta(texto)
    filtros = (
        {"turmas": turmas} if len(turmas) > 1 else ({"turma": turma} if turma else {})
    )
    if disciplina and aluno_termo and (vinculo or contagem or listagem):
        return {
            "tipo": (
                "disciplina_alunos_total" if contagem else "disciplina_alunos_lista"
            ),
            "disciplina": disciplina,
            "disciplinas": disciplinas,
            **filtros,
        }
    if (
        menciona_disciplina
        and not disciplina
        and re.search(
            r"\b(quais|qual|liste|listar|lista|mostre|existem|tem|temos|cadastradas|oferecidas|disponiveis|quantas|total|numero|quantidade)\b",
            texto,
        )
    ):
        return {
            "tipo": "disciplinas_total" if contagem else "disciplinas_lista",
            **filtros,
        }
    if (
        disciplina
        and re.search(r"\b(quais|qual|liste|listar|lista|mostre)\b", texto)
        and aluno_termo
    ):
        return {
            "tipo": "disciplina_alunos_lista",
            "disciplina": disciplina,
            "disciplinas": disciplinas,
            **filtros,
        }
    return None


def _disciplinas_registradas():
    """Catálogo inferido dos lançamentos, não de uma tabela de matrícula por disciplina."""
    valores = [d for (d,) in db.session.query(Nota.disciplina).distinct().all() if d]
    unicos = {}
    for valor in valores:
        unicos.setdefault(normalizar_pergunta(valor), str(valor).strip())
    return sorted(unicos.values(), key=normalizar_pergunta)


def _resposta_disciplinas(consulta):
    tipo = consulta["tipo"]
    disciplina = consulta.get("disciplina")
    disciplinas = consulta.get("disciplinas") or ([disciplina] if disciplina else [])
    turmas = consulta.get("turmas") or (
        [consulta["turma"]] if consulta.get("turma") else []
    )
    if tipo in ("disciplinas_lista", "disciplinas_total"):
        q = (
            db.session.query(Nota.disciplina)
            .join(Aluno, Nota.aluno_id == Aluno.id)
            .join(Turma, Aluno.turma_id == Turma.id)
        )
        if turmas:
            q = q.filter(Turma.nome.in_(turmas))
        valores = sorted(
            {str(d).strip() for (d,) in q.distinct().all() if d},
            key=normalizar_pergunta,
        )
        cabecalho = "## Disciplinas com notas registradas"
        contexto = f" nas turmas {', '.join(turmas)}" if turmas else ""
        if tipo == "disciplinas_total":
            return f"{cabecalho}\n\n**Total{contexto}:** {len(valores)} disciplinas."
        return "\n".join(
            [cabecalho, "", f"**Total{contexto}:** {len(valores)}", ""]
            + (
                [f"- {_md(d)}" for d in valores]
                if valores
                else ["Nenhuma disciplina com notas registradas."]
            )
            + ["", "*Disciplinas identificadas pelos lançamentos de notas.*"]
        )
    # DISTINCT por ID evita contar cada bimestre como aluno diferente.
    q = (
        db.session.query(Aluno.id, Aluno.nome, Aluno.matricula, Turma.nome)
        .join(Turma, Turma.id == Aluno.turma_id)
        .join(Nota, Nota.aluno_id == Aluno.id)
    )
    if turmas:
        q = q.filter(Turma.nome.in_(turmas))
    # Normalização da disciplina garante acentos/maiúsculas consistentes.
    variantes = [
        d
        for d in _disciplinas_registradas()
        if normalizar_pergunta(d) in {normalizar_pergunta(x) for x in disciplinas}
    ]
    if len({normalizar_pergunta(x) for x in variantes}) != len(
        {normalizar_pergunta(x) for x in disciplinas}
    ):
        return "Não encontrei registros para todas as disciplinas solicitadas."
    q = q.filter(Nota.disciplina.in_(variantes))
    # HAVING exige que o mesmo aluno possua lançamentos em TODAS as disciplinas.
    ids = [
        id_aluno
        for (id_aluno,) in (
            db.session.query(Nota.aluno_id)
            .filter(Nota.disciplina.in_(variantes))
            .group_by(Nota.aluno_id)
            .having(func.count(func.distinct(Nota.disciplina)) >= len(disciplinas))
            .all()
        )
    ]
    q = q.filter(Aluno.id.in_(ids))
    registros = q.distinct().order_by(Turma.nome, Aluno.nome, Aluno.id).all()
    titulo_disciplinas = " e ".join(disciplinas)
    total = len(registros)
    aviso = (
        "*Critério: alunos com pelo menos uma nota lançada nas disciplinas solicitadas. "
        "Sem uma tabela de matrículas por disciplina, não é possível afirmar que todos os demais não a cursam.*"
    )
    if tipo == "disciplina_alunos_total":
        return f"## Alunos com registros em {_md(titulo_disciplinas)}\n\n**Total de alunos distintos:** {total}\n\n{aviso}"
    return "\n".join(
        [
            f"## Alunos com registros em {_md(titulo_disciplinas)}",
            "",
            f"**Total:** {total}",
            "",
        ]
        + _tabela(
            ["Aluno", "Matrícula", "Turma"], [(r[1], r[2], r[3]) for r in registros]
        )
        + ["", aviso]
    )


def _consulta_filtro_alunos(pergunta):
    """Interpreta buscas textuais por matrícula, primeiro nome e sobrenome."""
    texto = normalizar_pergunta(pergunta)
    if not re.search(
        r"\b(aluno|alunos|estudante|estudantes|matricula|matriculas)\b", texto
    ):
        return None

    padroes = (
        (
            "matricula_sufixo",
            r"\bmatriculas?\s+(?:que\s+)?(?:termina|terminam|termine|terminem|acabam|acaba|finalizam|finaliza)\s+(?:com|em)\s+(\d+)\b",
        ),
        (
            "matricula_prefixo",
            r"\bmatriculas?\s+(?:que\s+)?(?:comeca|comecam|inicia|iniciam)\s+(?:com|em|por)\s+(\d+)\b",
        ),
        (
            "nome_prefixo",
            r"\bnomes?\s+(?:que\s+)?(?:comeca|comecam|inicia|iniciam|comece|iniciem)\s+(?:com|em|por)\s+(.+)$",
        ),
        (
            "nome_prefixo",
            r"\balunos?\s+(?:que\s+)?(?:comeca|comecam|inicia|iniciam)\s+(?:com|em|por)\s+(.+)$",
        ),
        ("sobrenome", r"\bsobrenomes?\s+(.+)$"),
        (
            "nome_contem",
            r"\bnomes?\s+(?:que\s+)?(?:contem|contenha|possui|possuem|tem|tenham)\s+(.+)$",
        ),
    )
    for criterio, padrao in padroes:
        match = re.search(padrao, texto)
        if match:
            valor = match.group(1).strip().rstrip(" ?.,")
            if valor:
                return {
                    "tipo": "alunos_filtro_textual",
                    "criterio": criterio,
                    "valor": valor,
                }
    return None


def _resposta_filtro_alunos(consulta):
    criterio, valor = consulta["criterio"], consulta["valor"]
    # Filtragem de matrícula diretamente no banco; nome normalizado em Python
    # para tratar corretamente acentos e maiúsculas no SQLite.
    q = db.session.query(Aluno.nome, Aluno.matricula, Turma.nome).join(
        Turma, Turma.id == Aluno.turma_id
    )
    if criterio == "matricula_sufixo":
        q = q.filter(Aluno.matricula.endswith(valor))
    elif criterio == "matricula_prefixo":
        q = q.filter(Aluno.matricula.startswith(valor))
    registros = q.order_by(Turma.nome, Aluno.nome).all()
    if criterio in ("nome_prefixo", "sobrenome", "nome_contem"):
        termo = normalizar_pergunta(valor)
        if criterio == "nome_prefixo":
            registros = [
                r for r in registros if normalizar_pergunta(r[0]).startswith(termo)
            ]
        elif criterio == "sobrenome":
            # Sobrenome como palavra completa após o primeiro nome.
            registros = [
                r
                for r in registros
                if re.search(
                    r"(?<!\w)" + re.escape(termo) + r"(?!\w)",
                    " ".join(normalizar_pergunta(r[0]).split()[1:]),
                )
            ]
        else:
            registros = [r for r in registros if termo in normalizar_pergunta(r[0])]
    descricoes = {
        "matricula_sufixo": f"matrícula terminada em {valor}",
        "matricula_prefixo": f"matrícula iniciada em {valor}",
        "nome_prefixo": f"nome iniciado por {valor}",
        "sobrenome": f"sobrenome {valor}",
        "nome_contem": f"nome contendo {valor}",
    }
    return "\n".join(
        [
            f"## Alunos com {descricoes[criterio]}",
            "",
            f"**Total encontrado:** {len(registros)}",
            "",
        ]
        + (
            _tabela(
                ["Aluno", "Matrícula", "Turma"], [(r[0], r[1], r[2]) for r in registros]
            )
            if registros
            else ["Nenhum aluno corresponde ao filtro informado."]
        )
    )


def identificar_consulta_escolar(pergunta):
    texto = normalizar_pergunta(pergunta)
    if not texto:
        return None
    if re.search(
        r"\b(iron maiden|musica|filme|futebol|politica|receita|clima|tempo hoje)\b",
        texto,
    ):
        return None
    consulta_filtro = _consulta_filtro_alunos(pergunta)
    if consulta_filtro:
        return consulta_filtro
    consulta_disciplina = _consulta_disciplinas(pergunta)
    if consulta_disciplina:
        return consulta_disciplina
    diagnostico = identificar_diagnostico_individual_ia(pergunta)
    if diagnostico:
        return diagnostico
    turma = _turma_pergunta(texto)
    turmas = _turmas_pergunta(texto)
    # Identificação de turma tem prioridade sobre total geral.
    if (
        turma
        and re.search(r"\b(alunos|estudantes|matriculados|matriculas)\b", texto)
        and re.search(
            r"\b(quantos|total|quantidade|numero|lista|liste|listar|quais|quem|nomes|mostre|relacao|possui|tem|ha)\b",
            texto,
        )
    ):
        tipo = (
            "lista_alunos"
            if re.search(
                r"\b(lista|liste|listar|quais|quem|nomes|mostre|relacao)\b", texto
            )
            else "total_alunos_turma"
        )
        return (
            {"tipo": tipo, "turmas": turmas}
            if len(turmas) > 1
            else {"tipo": tipo, "turma": turma}
        )
    total = _identificar_consulta_total_alunos(pergunta)
    if total:
        return total
    if re.search(r"\b(turma|turmas)\b", texto) and not re.search(
        r"\b(nota|notas|media|medias|frequencia|presenca|faltas|ausencias)\b", texto
    ):
        if (
            re.search(r"\b(quantas|quantos|total|quantidade|numero)\b", texto)
            and not turma
        ):
            return {"tipo": "total_turmas"}
        if re.search(
            r"\b(mais alunos|maior turma|mais cheia|menos alunos|menor turma|menos cheia)\b",
            texto,
        ):
            return {
                "tipo": "ranking_turmas",
                "ordem": "asc" if re.search(r"\b(menos|menor)\b", texto) else "desc",
            }
        return {"tipo": "lista_turmas", **({"turma": turma} if turma else {})}
    if (
        re.search(r"\b(alunos|estudantes|matriculas|matriculados)\b", texto)
        and re.search(r"\b(listar|liste|lista|quais|nomes|relacao|mostre)\b", texto)
        and not re.search(r"\b(notas|media|frequencia|faltas)\b", texto)
    ):
        return {"tipo": "lista_alunos", **({"turma": turma} if turma else {})}
    if re.search(
        r"\b(matricula|matricula do|matricula da|qual turma|em que turma|dados do aluno|dados da aluna)\b",
        texto,
    ):
        aluno = _aluno_na_pergunta(texto)
        if aluno:
            return {"tipo": "dados_aluno", **aluno}
    notas = _identificar_consulta_notas(pergunta)
    if notas:
        return notas
    tem_freq = bool(
        re.search(
            r"\b(frequencia|presenca|presencas|assiduidade|falta|faltas|ausencia|ausencias)\b",
            texto,
        )
    )
    if tem_freq:
        aluno = _aluno_na_pergunta(texto)
        percentual = _percentual_pergunta(texto)
        if (
            re.search(r"\b(turma|turmas)\b", texto)
            and re.search(r"\b(menor|pior|mais baixa|maior|melhor|mais alta)\b", texto)
            and percentual is None
            and not turma
        ):
            return {
                "tipo": (
                    "turma_menor_frequencia"
                    if re.search(r"\b(menor|pior|mais baixa)\b", texto)
                    else "turma_maior_frequencia"
                )
            }
        if (
            re.search(
                r"\b(mais faltas|maior numero de faltas|mais ausencias|maior quantidade de faltas|ranking de faltas)\b",
                texto,
            )
            and not aluno
        ):
            return {
                "tipo": "ranking_faltas",
                "limite": 10,
                **({"turma": turma} if turma else {}),
            }
        if percentual is not None:
            direcao = _direcao_frequencia(texto)
            if direcao:
                return {
                    "tipo": direcao,
                    "limite": percentual,
                    **({"turma": turma} if turma else {}),
                }
        if aluno:
            return {"tipo": "frequencia_aluno", **aluno}
        return {"tipo": "frequencia_resumo", **({"turma": turma} if turma else {})}
    if re.search(r"\b(ano letivo|anos letivos)\b", texto):
        return {"tipo": "lista_turmas"}
    return None


def _aplicar_continuacao_frequencia(pergunta, consulta_anterior):
    if not consulta_anterior or consulta_anterior.get("tipo") not in (
        "frequencia_abaixo",
        "frequencia_acima",
        "frequencia_resumo",
    ):
        return None
    texto = normalizar_pergunta(pergunta)
    if not re.match(
        r"^(e\b|mas\b|agora\b|somente\b|apenas\b|so\b|da turma\b|na turma\b)", texto
    ):
        return None
    turma, percentual = _turma_pergunta(texto), _percentual_pergunta(texto)
    if turma is None and percentual is None:
        return None
    nova = dict(consulta_anterior)
    if turma:
        nova["turma"] = turma
    if percentual is not None:
        nova["limite"] = percentual
        direcao = _direcao_frequencia(texto)
        if direcao:
            nova["tipo"] = direcao
    return nova


def _aplicar_continuacao_notas(pergunta, consulta_anterior):
    if not consulta_anterior or not consulta_anterior.get("tipo", "").startswith(
        "notas_"
    ):
        return None
    texto = normalizar_pergunta(pergunta)
    if not re.match(
        r"^(e\b|mas\b|agora\b|somente\b|apenas\b|so\b|da turma\b|na turma\b)", texto
    ):
        return None
    turma, disciplina = _turma_pergunta(texto), _disciplina_pergunta(texto)
    if not turma and not disciplina:
        return None
    nova = dict(consulta_anterior)
    if turma:
        nova["turma"] = turma
    if disciplina:
        nova["disciplina"] = disciplina
    return nova


def identificar_consulta_escolar_contextual(pergunta, historico=None):
    consulta = identificar_consulta_escolar(pergunta)
    if consulta is not None:
        return consulta
    texto = normalizar_pergunta(pergunta)
    if not re.match(
        r"^(e\b|mas\b|agora\b|somente\b|apenas\b|so\b|da turma\b|na turma\b)", texto
    ):
        return None
    mensagens = [
        m.get("content", "") for m in (historico or []) if m.get("role") == "user"
    ]
    contexto = None
    for mensagem in mensagens[-10:]:
        nova = identificar_consulta_escolar(mensagem)
        if nova is not None:
            contexto = nova
        else:
            contexto = _aplicar_continuacao_notas(
                mensagem, contexto
            ) or _aplicar_continuacao_frequencia(mensagem, contexto)
    return _aplicar_continuacao_notas(
        pergunta, contexto
    ) or _aplicar_continuacao_frequencia(pergunta, contexto)


def obter_dados_diagnostico_individual_ia(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if aluno is None:
        return None
    desempenho = next(
        (x for x in obter_desempenho_alunos_ia() if x["aluno_id"] == aluno_id), None
    )
    frequencia = next(
        (x for x in obter_frequencia_alunos_ia() if x["aluno_id"] == aluno_id), None
    )
    if desempenho is None:
        return None
    disciplinas = [
        {
            "disciplina": d["nome_exibicao"],
            "media": round(d["media"], 2),
            "bimestres_registrados": d["bimestres_registrados"],
            "abaixo_referencia": d["media"] < MEDIA_REFERENCIA_IA,
        }
        for d in desempenho["disciplinas"].values()
    ]
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
        "disciplinas": sorted(disciplinas, key=lambda d: d["disciplina"]),
        "frequencia": frequencia,
        "media_referencia": MEDIA_REFERENCIA_IA,
        "referencia_frequencia": FREQUENCIA_REFERENCIA_IA,
    }


def _mensagem_aluno(consulta):
    if consulta.get("ambiguidade"):
        return "\n".join(
            ["Encontrei mais de um aluno. Informe o nome completo:", ""]
            + [
                f"- **{_md(a['nome'])}** — turma {_md(a['turma'])}"
                for a in consulta["ambiguidade"]
            ]
        )
    if consulta.get("aluno_nao_identificado") or not consulta.get("aluno_id"):
        return (
            f"Não encontrei o aluno **{_md(consulta['nome_buscado'])}**. Confira o nome ou a matrícula."
            if consulta.get("nome_buscado")
            else "Informe o nome completo do aluno."
        )
    return None


def gerar_diagnostico_individual_ia(consulta):
    erro = _mensagem_aluno(consulta)
    if erro:
        return erro
    dados = obter_dados_diagnostico_individual_ia(consulta["aluno_id"])
    if not dados:
        return "Aluno não encontrado."
    linhas = [
        f"## Diagnóstico pedagógico — {_md(dados['aluno'])}",
        "",
        f"**Turma:** {_md(dados['turma'])}  ",
        f"**Matrícula:** {_md(dados['matricula'])}  ",
        (
            f"**Média geral:** {dados['media_geral']:.2f}"
            if dados["media_geral"] is not None
            else "**Média geral:** sem notas"
        ),
        "",
        "### Desempenho por disciplina",
        "",
    ]
    linhas.extend(
        _tabela(
            ["Disciplina", "Média", "Bimestres", "Indicador"],
            [
                (
                    d["disciplina"],
                    f"{d['media']:.2f}",
                    f"{d['bimestres_registrados']}/4",
                    "Abaixo de 6,0" if d["abaixo_referencia"] else "6,0 ou superior",
                )
                for d in dados["disciplinas"]
            ],
        )
    )
    if not dados["disciplinas"]:
        linhas.append("Nenhuma nota registrada.")
    f = dados["frequencia"]
    linhas.extend(["", "### Frequência", ""])
    if f and f["percentual_frequencia"] is not None:
        linhas.extend(
            [
                f"**Frequência registrada:** {f['percentual_frequencia']:.2f}%  ",
                f"**Presenças:** {f['presencas']} · **Faltas:** {f['faltas']} · **Registros:** {f['total_registros']}",
            ]
        )
    else:
        linhas.append("Sem registros de frequência.")
    pontos = []
    abaixo = [d["disciplina"] for d in dados["disciplinas"] if d["abaixo_referencia"]]
    if abaixo:
        pontos.append("Médias abaixo de 6,0 em: " + ", ".join(abaixo) + ".")
    if f and f["percentual_frequencia"] is not None and f["percentual_frequencia"] < 75:
        pontos.append("Frequência abaixo da referência de acompanhamento de 75%.")
    if f and 0 < f["total_registros"] < 10:
        pontos.append("Poucos registros de frequência: o percentual exige cautela.")
    if any(d["bimestres_registrados"] < 4 for d in dados["disciplinas"]):
        pontos.append(
            "Há disciplinas com menos de quatro bimestres; as médias são parciais."
        )
    if not dados["disciplinas"]:
        pontos.append("Não há notas suficientes para avaliar o desempenho.")
    if not pontos:
        pontos.append(
            "Nenhum indicador abaixo das referências nos registros disponíveis."
        )
    linhas.extend(["", "### Pontos de atenção", ""] + ["- " + p for p in pontos])
    linhas.extend(
        [
            "",
            "### Encaminhamentos sugeridos",
            "",
            "Conferir os registros com a equipe pedagógica e acompanhar a evolução por disciplina e a assiduidade.",
            "",
            "**Observação:** análise descritiva dos dados existentes; não constitui diagnóstico clínico nem determina aprovação ou reprovação.",
        ]
    )
    return "\n".join(linhas)


def _filtrar_turma(registros, turma):
    return (
        [
            r
            for r in registros
            if normalizar_pergunta(r["turma"]) == normalizar_pergunta(turma)
        ]
        if turma
        else registros
    )


def _gerar_resposta_notas(consulta):
    tipo = consulta["tipo"]
    turma, disciplina, bimestre = (
        consulta.get("turma"),
        consulta.get("disciplina"),
        consulta.get("bimestre"),
    )
    if tipo == "notas_media_geral":
        q = db.session.query(func.avg(Nota.valor), func.count(Nota.id))
        if turma:
            q = (
                q.join(Aluno, Aluno.id == Nota.aluno_id)
                .join(Turma, Turma.id == Aluno.turma_id)
                .filter(Turma.nome == turma)
            )
        if disciplina:
            variantes = [
                d
                for d in _disciplinas_registradas()
                if normalizar_pergunta(d) == normalizar_pergunta(disciplina)
            ]
            q = q.filter(Nota.disciplina.in_(variantes))
        media_geral, quantidade = q.one()
        if not quantidade:
            return "Não há notas registradas para os filtros informados."
        escopo = f" de {disciplina}" if disciplina else ""
        escopo += f" na turma {turma}" if turma else ""
        return f"## Média geral das notas{escopo}\n\n**Média:** {float(media_geral):.2f} / 10\n\n**Lançamentos considerados:** {quantidade}\n\n*Média aritmética dos lançamentos de notas registrados.*"
    if tipo in ("notas_listagem", "notas_total") or bimestre is not None:
        q = (
            db.session.query(Nota, Aluno.nome, Turma.nome)
            .join(Aluno, Nota.aluno_id == Aluno.id)
            .join(Turma, Aluno.turma_id == Turma.id)
        )
        if turma:
            q = q.filter(Turma.nome == turma)
        if disciplina:
            q = q.filter(func.lower(Nota.disciplina) == disciplina.lower())
        if bimestre:
            q = q.filter(Nota.bimestre == bimestre)
        registros = q.order_by(Aluno.nome, Nota.disciplina, Nota.bimestre).all()
        if tipo == "notas_total":
            return f"## Notas lançadas\n\n**Total de registros:** {len(registros)}" + (
                f"\n\n**Turma:** {turma}" if turma else ""
            )
        linhas = ["## Notas registradas", "", f"**Registros:** {len(registros)}", ""]
        linhas.extend(
            _tabela(
                ["Aluno", "Turma", "Disciplina", "Bimestre", "Nota"],
                [
                    (nome, t, n.disciplina, n.bimestre, f"{n.valor:.2f}")
                    for n, nome, t in registros
                ],
            )
        )
        return "\n".join(linhas)
    alunos = _filtrar_turma(obter_desempenho_alunos_ia(), turma)
    if consulta.get("aluno_id"):
        alunos = [a for a in alunos if a["aluno_id"] == consulta["aluno_id"]]
    elif consulta.get("ambiguidade") or consulta.get("aluno_nao_identificado"):
        return _mensagem_aluno(consulta)
    chave = normalizar_pergunta(disciplina) if disciplina else None

    def media(a):
        return (
            a["disciplinas"].get(chave, {}).get("media") if chave else a["media_geral"]
        )

    validos = [a for a in alunos if media(a) is not None]
    if "frequencia_abaixo" in consulta:
        f = {x["aluno_id"]: x for x in obter_frequencia_alunos_ia()}
        validos = [
            a
            for a in validos
            if f.get(a["aluno_id"], {}).get("percentual_frequencia") is not None
            and f[a["aluno_id"]]["percentual_frequencia"]
            < consulta["frequencia_abaixo"]
        ]
    if tipo == "notas_sem_registro":
        selecionados = [a for a in alunos if media(a) is None]
    elif tipo in ("notas_abaixo", "notas_acima"):
        limite = float(consulta["limite"])
        selecionados = [
            a
            for a in validos
            if (media(a) < limite if tipo == "notas_abaixo" else media(a) > limite)
        ]
    else:
        selecionados = validos
    if tipo == "notas_turmas":
        grupos = defaultdict(list)
        for a in selecionados:
            grupos[a["turma"]].append(media(a))
        valores = [(t, sum(v) / len(v), len(v)) for t, v in grupos.items()]
        valores.sort(key=lambda x: x[1], reverse=consulta.get("ordem") != "asc")
        return "\n".join(
            ["## Médias por turma", ""]
            + _tabela(
                ["Turma", "Média", "Alunos com notas"],
                [(t, f"{m:.2f}", qtd) for t, m, qtd in valores],
            )
        )
    if tipo == "notas_ranking":
        selecionados.sort(
            key=lambda a: (media(a), a["aluno"]), reverse=consulta.get("ordem") != "asc"
        )
        selecionados = selecionados[:10]
    elif tipo == "notas_sem_registro":
        selecionados.sort(key=lambda a: a["aluno"])
    else:
        selecionados.sort(key=lambda a: a["aluno"])
    if tipo == "notas_aluno" and selecionados:
        a = selecionados[0]
        linhas = [
            f"## Notas de {a['aluno']}",
            "",
            f"**Turma:** {a['turma']}",
            "",
            (
                f"**Média geral:** {a['media_geral']:.2f}"
                if a["media_geral"] is not None
                else "**Média geral:** sem notas"
            ),
            "",
        ]
        linhas.extend(
            _tabela(
                ["Disciplina", "Média", "Bimestres"],
                [
                    (
                        d["nome_exibicao"],
                        f"{d['media']:.2f}",
                        d["bimestres_registrados"],
                    )
                    for d in a["disciplinas"].values()
                ],
            )
        )
        return "\n".join(linhas)
    titulo = {
        "notas_abaixo": "Médias abaixo do limite",
        "notas_acima": "Médias acima do limite",
        "notas_ranking": "Ranking de médias",
        "notas_sem_registro": "Alunos sem notas",
        "notas_resumo": "Médias dos alunos",
    }.get(tipo, "Desempenho escolar")
    if disciplina:
        titulo += f" — {disciplina}"
    linhas = [
        f"## {titulo}",
        "",
        f"**Alunos analisados:** {len(alunos)}",
        f"**Resultados:** {len(selecionados)}",
        "",
    ]
    linhas.extend(
        _tabela(
            ["Aluno", "Turma", "Média", "Disciplinas com notas"],
            [
                (
                    a["aluno"],
                    a["turma"],
                    f"{media(a):.2f}" if media(a) is not None else "Sem notas",
                    a["total_disciplinas"],
                )
                for a in selecionados
            ],
        )
    )
    if tipo in ("notas_abaixo", "notas_acima"):
        linhas.extend(
            [
                "",
                f"*Limite aplicado: {float(consulta['limite']):.2f} na escala de 0 a 10.*",
            ]
        )
    linhas.extend(
        [
            "",
            "*Médias calculadas apenas com notas registradas; disciplinas sem nota não contam como zero.*",
        ]
    )
    return "\n".join(linhas)


def gerar_resposta_consulta_escolar(consulta):
    tipo = consulta["tipo"]
    turma = consulta.get("turma")
    if tipo == "alunos_filtro_textual":
        return _resposta_filtro_alunos(consulta)
    if tipo in (
        "disciplinas_lista",
        "disciplinas_total",
        "disciplina_alunos_lista",
        "disciplina_alunos_total",
    ):
        return _resposta_disciplinas(consulta)
    if tipo == "total_alunos":
        total = db.session.query(func.count(Aluno.id)).scalar() or 0
        return f"## Total de alunos cadastrados\n\nAtualmente, o EscolaIA possui **{total} alunos cadastrados**.\n\n*Informação consultada diretamente no banco de dados.*"
    if tipo == "total_turmas":
        return f"## Total de turmas\n\nO EscolaIA possui **{Turma.query.count()} turmas cadastradas**."
    if tipo in ("total_alunos_turma", "lista_turmas", "ranking_turmas"):
        distribuicao = obter_distribuicao_alunos_ia()
        if tipo == "total_alunos_turma":
            solicitadas = consulta.get("turmas") or ([turma] if turma else [])
            itens = []
            for codigo in solicitadas:
                correspondentes = [
                    x
                    for x in distribuicao
                    if normalizar_pergunta(x["turma"]) == normalizar_pergunta(codigo)
                ]
                if not correspondentes:
                    return f"Não encontrei a turma **{_md(codigo)}** cadastrada."
                if len(correspondentes) > 1:
                    return f"Há mais de uma turma **{_md(codigo)}** em anos letivos diferentes. Informe também o ano letivo."
                itens.append(correspondentes[0])
            if len(itens) == 1:
                return f"## Total de alunos — Turma {_md(itens[0]['turma'])}\n\nA turma **{_md(itens[0]['turma'])}** possui **{itens[0]['total_alunos']} alunos cadastrados**."
            total = sum(x["total_alunos"] for x in itens)
            return "\n".join(
                ["## Total de alunos por turma", ""]
                + _tabela(
                    ["Turma", "Alunos"],
                    [(x["turma"], x["total_alunos"]) for x in itens],
                )
                + ["", f"**Total combinado:** {total} alunos."]
            )
        if tipo == "ranking_turmas":
            distribuicao.sort(
                key=lambda x: x["total_alunos"], reverse=consulta.get("ordem") != "asc"
            )
        if turma:
            distribuicao = [
                x
                for x in distribuicao
                if normalizar_pergunta(x["turma"]) == normalizar_pergunta(turma)
            ]
        return "\n".join(
            ["## Turmas cadastradas", "", f"**Total:** {len(distribuicao)}", ""]
            + _tabela(
                ["Turma", "Ano letivo", "Alunos"],
                [
                    (x["turma"], x["ano_letivo"], x["total_alunos"])
                    for x in distribuicao
                ],
            )
        )
    if tipo == "lista_alunos":
        q = db.session.query(Aluno.nome, Aluno.matricula, Turma.nome).join(
            Turma, Turma.id == Aluno.turma_id
        )
        turmas_solicitadas = consulta.get("turmas") or ([turma] if turma else [])
        if turmas_solicitadas:
            q = q.filter(Turma.nome.in_(turmas_solicitadas))
        alunos = q.order_by(Turma.nome, Aluno.nome).all()
        descricao = ", ".join(turmas_solicitadas)
        return "\n".join(
            [
                "## Alunos cadastrados"
                + (f" — turma(s) {descricao}" if descricao else ""),
                "",
                f"**Total:** {len(alunos)}",
                "",
            ]
            + _tabela(
                ["Aluno", "Matrícula", "Turma"], [(a[0], a[1], a[2]) for a in alunos]
            )
        )
    if tipo == "dados_aluno":
        erro = _mensagem_aluno(consulta)
        if erro:
            return erro
        a = db.session.get(Aluno, consulta["aluno_id"])
        return (
            f"## Dados de {a.nome}\n\n**Matrícula:** {a.matricula}  \n**Turma:** {a.turma.nome}  \n**Ano letivo:** {a.turma.ano_letivo}"
            if a
            else "Aluno não encontrado."
        )
    if tipo == "diagnostico_aluno":
        return gerar_diagnostico_individual_ia(consulta)
    if tipo.startswith("notas_"):
        return _gerar_resposta_notas(consulta)
    if tipo in (
        "frequencia_abaixo",
        "frequencia_acima",
        "frequencia_aluno",
        "frequencia_resumo",
        "ranking_faltas",
        "turma_menor_frequencia",
        "turma_maior_frequencia",
    ):
        frequencias = _filtrar_turma(obter_frequencia_alunos_ia(), turma)
        if tipo == "frequencia_aluno":
            erro = _mensagem_aluno(consulta)
            if erro:
                return erro
            frequencias = [
                f for f in frequencias if f["aluno_id"] == consulta["aluno_id"]
            ]
        if tipo in ("frequencia_abaixo", "frequencia_acima"):
            limite = float(consulta["limite"])
            if not 0 <= limite <= 100:
                return "O percentual deve estar entre 0% e 100%."
            frequencias = [
                f
                for f in frequencias
                if f["percentual_frequencia"] is not None
                and (
                    f["percentual_frequencia"] < limite
                    if tipo == "frequencia_abaixo"
                    else f["percentual_frequencia"] > limite
                )
            ]
            frequencias.sort(
                key=lambda f: f["percentual_frequencia"],
                reverse=tipo == "frequencia_acima",
            )
            titulo = f"Frequência {'abaixo' if tipo == 'frequencia_abaixo' else 'acima'} de {limite:g}%"
        elif tipo == "ranking_faltas":
            frequencias = sorted(
                [f for f in frequencias if f["total_registros"] > 0],
                key=lambda f: (-f["faltas"], f["aluno"]),
            )[:10]
            titulo = "Alunos com mais faltas"
        elif tipo in ("turma_menor_frequencia", "turma_maior_frequencia"):
            grupos = defaultdict(lambda: {"presencas": 0, "registros": 0, "alunos": 0})
            for f in frequencias:
                g = grupos[f["turma"]]
                g["presencas"] += f["presencas"]
                g["registros"] += f["total_registros"]
                g["alunos"] += 1
            dados = [(t, g) for t, g in grupos.items() if g["registros"]]
            dados.sort(
                key=lambda x: x[1]["presencas"] / x[1]["registros"],
                reverse=tipo == "turma_maior_frequencia",
            )
            if not dados:
                return "Não há registros de frequência suficientes para comparar as turmas."
            return "\n".join(
                ["## Frequência por turma", ""]
                + _tabela(
                    ["Turma", "Frequência", "Presenças", "Registros", "Alunos"],
                    [
                        (
                            t,
                            f"{g['presencas']/g['registros']*100:.2f}%",
                            g["presencas"],
                            g["registros"],
                            g["alunos"],
                        )
                        for t, g in dados
                    ],
                )
                + [
                    "",
                    f"**Turma em destaque:** {dados[0][0]}",
                    "",
                    "*Critério: presenças divididas pelos registros de cada turma.*",
                ]
            )
        else:
            titulo = "Frequência escolar" + (f" — turma {turma}" if turma else "")
        return "\n".join(
            [f"## {titulo}", "", f"**Alunos encontrados:** {len(frequencias)}", ""]
            + _tabela_frequencia_ia(frequencias)
            + [
                "",
                "*Frequência calculada apenas sobre os registros existentes; poucos registros exigem cautela.*",
            ]
        )
    raise ValueError(f"Tipo de consulta escolar não reconhecido: {tipo}")
