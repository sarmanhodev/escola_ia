import json
import requests

URL_OLLAMA = "http://localhost:11434/api/chat"
MODELO_IA = "qwen3:1.7b"
TIMEOUT_OLLAMA = 120
LIMITE_HISTORICO = 6


def montar_contexto_escolar(contexto_escolar):
    if not contexto_escolar:
        return ""
    linhas = [
        "DADOS REAIS DO SISTEMA ESCOLAIA:",
        f"Total de alunos: {contexto_escolar.get('total_alunos', 0)}",
        f"Total de turmas: {contexto_escolar.get('total_turmas', 0)}",
        "",
        "DISTRIBUIÇÃO DOS ALUNOS POR TURMA:",
    ]
    for turma in contexto_escolar.get("distribuicao_turmas", []):
        linhas.append(
            f"- Turma {turma['turma']} ({turma['ano_letivo']}): {turma['total_alunos']} alunos"
        )
    linhas.extend(["", "MÉDIAS DAS TURMAS:"])
    for turma in contexto_escolar.get("medias_turmas", []):
        media = turma.get("media_notas")
        quantidade = turma.get("total_notas", 0)
        if media is None:
            linhas.append(f"- Turma {turma['turma']}: sem notas lançadas")
        else:
            linhas.append(
                f"- Turma {turma['turma']}: média {media:.2f}; {quantidade} notas lançadas"
            )
    linhas.extend(
        [
            "",
            "REGRAS DE INTERPRETAÇÃO:",
            "- Utilize somente os dados fornecidos.",
            "- Não invente alunos, notas ou estatísticas.",
            "- As médias acima representam lançamentos de notas, não médias individuais.",
            "- Considere a quantidade de notas ao comparar turmas.",
            "- Não conclua aprovação ou reprovação sem critérios.",
            "- Se os dados forem insuficientes, informe isso.",
        ]
    )
    return "\n".join(linhas)


def montar_contexto_frequencia(contexto_escolar):
    if not contexto_escolar:
        return ""
    consulta = contexto_escolar.get("consulta_frequencia")
    if not isinstance(consulta, dict):
        return ""
    limite = consulta.get("limite", 75)
    total_analisados = consulta.get("total_analisados", 0)
    total_encontrados = consulta.get("total_encontrados", 0)
    alunos = consulta.get("alunos", [])
    linhas = [
        "CONSULTA DE FREQUÊNCIA EXECUTADA PELO FLASK:",
        f"Critério: frequência inferior a {limite}%.",
        f"Total de alunos analisados: {total_analisados}",
        f"Total abaixo do limite: {total_encontrados}",
        "RESULTADOS:",
    ]
    linhas.extend(alunos if alunos else ["Nenhum aluno encontrado."])
    linhas.extend(
        [
            "Não recalcule os percentuais nem invente registros.",
            "Não determine reprovação automaticamente.",
        ]
    )
    return "\n".join(linhas)


def montar_mensagens(pergunta, historico=None, contexto_escolar=None):
    conteudo_sistema = (
        "Você é o assistente inteligente do EscolaIA, sistema de gestão escolar.\n"
        "Responda em português brasileiro, com clareza e objetividade.\n"
        "Use somente dados reais fornecidos. Não invente alunos, notas, turmas ou frequência.\n"
        "Não confunda exemplos com dados reais. Se faltarem dados, explique."
    )
    contexto_geral = montar_contexto_escolar(contexto_escolar)
    contexto_frequencia = montar_contexto_frequencia(contexto_escolar)
    if contexto_geral:
        conteudo_sistema += "\n\n" + contexto_geral
    if contexto_frequencia:
        conteudo_sistema += "\n\n" + contexto_frequencia
    mensagens = [{"role": "system", "content": conteudo_sistema}]
    historico_valido = []
    for mensagem in historico or []:
        if not isinstance(mensagem, dict):
            continue
        papel, conteudo = mensagem.get("role"), mensagem.get("content")
        if (
            papel in ("user", "assistant")
            and isinstance(conteudo, str)
            and conteudo.strip()
        ):
            historico_valido.append({"role": papel, "content": conteudo})
    mensagens.extend(historico_valido[-LIMITE_HISTORICO:])
    mensagens.append({"role": "user", "content": pergunta})
    return mensagens


def _chamar_ollama(mensagens, num_predict=400):
    dados = {
        "model": MODELO_IA,
        "messages": mensagens,
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096, "num_predict": num_predict, "temperature": 0.2},
    }
    resposta = requests.post(URL_OLLAMA, json=dados, timeout=(10, TIMEOUT_OLLAMA))
    resposta.raise_for_status()
    resultado = resposta.json()
    return (resultado.get("message", {}).get("content") or "").strip()


def perguntar_ia(pergunta, historico=None, contexto_escolar=None):
    return _chamar_ollama(montar_mensagens(pergunta, historico, contexto_escolar))


def _fatos_pedagogicos_verificados(dados):
    """Constrói afirmações autorizadas exclusivamente com dados calculados no Flask."""
    disciplinas = dados.get("disciplinas") or []
    frequencia = dados.get("frequencia") or {}
    media = dados.get("media_geral")
    referencia_media = float(dados.get("media_referencia", 6.0))
    referencia_frequencia = float(dados.get("referencia_frequencia", 75.0))
    registros = int(frequencia.get("total_registros") or 0)
    percentual = frequencia.get("percentual_frequencia")
    incompletas = [
        d for d in disciplinas if int(d.get("bimestres_registrados") or 0) < 4
    ]
    abaixo = [
        d["disciplina"]
        for d in disciplinas
        if d.get("media") is not None and float(d["media"]) < referencia_media
    ]

    fatos = []
    if media is not None:
        situacao = "abaixo" if float(media) < referencia_media else "igual ou acima"
        fatos.append(
            f"A média registrada do aluno é {float(media):.2f}, {situacao} "
            f"da referência de {referencia_media:.1f}."
        )
    else:
        fatos.append("Não há média geral disponível nos registros apresentados.")

    if abaixo:
        fatos.append(
            "As disciplinas com médias abaixo da referência são: "
            + ", ".join(abaixo)
            + "."
        )
    elif disciplinas:
        fatos.append(
            "Nenhuma das disciplinas registradas está abaixo da referência adotada."
        )

    if incompletas:
        fatos.append(
            "Há disciplinas com bimestres ainda não registrados; "
            "as médias apresentadas são parciais."
        )
    if len(disciplinas) == 1:
        fatos.append(
            "Há notas de apenas uma disciplina, o que não permite avaliar "
            "o desempenho acadêmico de forma abrangente."
        )
    elif not disciplinas:
        fatos.append("Não há disciplinas com notas disponíveis para avaliação.")

    if percentual is not None and registros > 0:
        situacao = (
            "abaixo" if float(percentual) < referencia_frequencia else "igual ou acima"
        )
        fatos.append(
            f"A frequência registrada é {float(percentual):.2f}%, {situacao} "
            f"da referência de {referencia_frequencia:.1f}%."
        )
    else:
        fatos.append("Não há registros suficientes para calcular a frequência.")

    if 0 < registros < 10:
        fatos.append(
            f"Existem somente {registros} registro(s) de frequência; "
            "não é possível concluir que a assiduidade seja regular."
        )
    elif registros == 0:
        fatos.append("Não há registros de frequência para avaliar a assiduidade.")

    fatos.append(
        "Recomenda-se conferir os lançamentos e acompanhar a evolução "
        "das notas e da frequência junto à equipe pedagógica."
    )
    return fatos


def _selecionar_fatos_ia(dados):
    """O Qwen3 só seleciona IDs. Nunca escreve números ou afirmações para o relatório."""
    fatos = _fatos_pedagogicos_verificados(dados)
    opcoes = [{"id": i, "texto": fato} for i, fato in enumerate(fatos)]
    mensagens = [
        {
            "role": "system",
            "content": (
                "Você seleciona fatos verificados para um relatório pedagógico. "
                'Responda SOMENTE JSON no formato {\\"ids\\":[0,1,2]}. '
                "Selecione até 5 IDs relevantes da lista recebida, sem criar textos, "
                "sem calcular valores e sem incluir IDs inexistentes. "
                "Priorize ressalvas sobre registros insuficientes."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"fatos_permitidos": opcoes}, ensure_ascii=False),
        },
    ]
    texto = _chamar_ollama(mensagens, num_predict=100)
    try:
        selecao = json.loads(texto)
        ids = selecao.get("ids", [])
        if not isinstance(ids, list):
            raise ValueError("Lista de IDs inválida")
        validos = []
        for item in ids:
            if type(item) is int and 0 <= item < len(fatos) and item not in validos:
                validos.append(item)
        if not validos:
            raise ValueError("Nenhum fato válido selecionado")
        return fatos, validos[:5]
    except (ValueError, TypeError, AttributeError):
        # Saída fora do formato? Retorna os fatos determinísticos, sem confiar na IA.
        return fatos, list(range(min(5, len(fatos))))


def interpretar_diagnostico_pedagogico(dados):
    """Produz análise rastreável; nenhuma afirmação livre do LLM é publicada."""
    fatos, selecionados = _selecionar_fatos_ia(dados)
    # Inclui ressalvas críticas mesmo quando a IA não as seleciona.
    criticos = [
        i
        for i, fato in enumerate(fatos)
        if (
            "não permite avaliar" in fato
            or "não é possível concluir" in fato
            or "médias apresentadas são parciais" in fato
            or "Não há registros" in fato
        )
    ]
    indices = sorted(set(selecionados + criticos))
    return "\n\n".join(fatos[i] for i in indices)
