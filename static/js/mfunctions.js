let conversaAtualIA = null;
let boasVindasChatIA = null;

// Funções reutilizáveis do EscolaIA.
function filtrarAlunos(termo) {
    const busca = String(termo || '').toLocaleLowerCase('pt-BR').trim();
    $('#tabelaAlunos tbody tr').each(function () {
        const texto = $(this).text().toLocaleLowerCase('pt-BR');
        $(this).toggle(texto.includes(busca));
    });
}

function iniciarTemporizadoresAlertas() {
    $('#containerMensagensSistema .alertaSistema').each(function () {
        const elemento = this;
        const tempo = Number($(elemento).attr('data-tempo')) || 4000;
        window.setTimeout(function () {
            if (elemento.isConnected) {
                bootstrap.Alert.getOrCreateInstance(elemento).close();
            }
        }, tempo);
    });
}

function excluirAluno(idAluno) {

    $.ajax({
        type: "POST",
        url: `/alunos/${idAluno}/excluir`,
        dataType: "json",

        beforeSend: function () {
            $(`.btnExcluirAluno[id-aluno="${idAluno}"]`)
                .prop("disabled", true)
                .text("Excluindo...");
        },

        success: function (response) {
            $("#modalConfirmarExclusaoAluno").modal("hide");

            if (response.success) {

                $(`#linhaAluno${response.idAluno}`).fadeOut(300, function () {
                    $(this).remove();
                });

                exibirMensagemSistema(response.message, "success");

            } else {
                exibirMensagemSistema(response.message, "danger");
            }
        },

        error: function (xhr) {

            const mensagem = xhr.responseJSON?.message
                || "Erro ao excluir o aluno.";

            exibirMensagemSistema(mensagem, "danger");
        },

        complete: function () {

            $(`.btnExcluirAluno[id-aluno="${idAluno}"]`)
                .prop("disabled", false)
                .text("Excluir");
        }
    });
}

function exibirMensagemSistema(mensagem, tipo = "success") {

    const $alerta = $("<div>", {
        class: `alert alert-${tipo} alert-dismissible fade show alertaSistema`,
        role: "alert",
        "data-tempo": 4000
    });

    $("<span>").text(mensagem).appendTo($alerta);

    $("<button>", {
        type: "button",
        class: "btn-close",
        "data-bs-dismiss": "alert",
        "aria-label": "Fechar"
    }).appendTo($alerta);

    $("#containerMensagensSistema").append($alerta);

    setTimeout(function () {
        if ($alerta[0].isConnected) {
            bootstrap.Alert.getOrCreateInstance($alerta[0]).close();
        }
    }, 4000);
}

function confirmarExclusaoAluno() {
    return window.confirm(
        "Excluir aluno e seus registros de notas e frequência?"
    );
}


function carregarDadosEdicaoAluno(idAluno) {

    $.ajax({
        type: "GET",
        url: `/alunos/${idAluno}/dados`,
        dataType: "json",

        beforeSend: function () {
            $("#modalEditarRegistro").modal('show');

            $("#nomeAlunoEdicao").val("");

            $("#turmaAlunoEdicao")
                .empty()
                .append('<option value="">Carregando...</option>');

            $("#btnSalvarEdicaoAluno").prop("disabled", true);
        },

        success: function (response) {

            if (!response.success) {
                exibirMensagemSistema(
                    response.message || "Erro ao carregar aluno.",
                    "danger"
                );
                return;
            }

            const aluno = response.aluno;

            $("#btnSalvarEdicaoAluno").attr("id-aluno", aluno.id);
            $("#nomeAlunoEdicao").val(aluno.nome);

            const $combo = $("#turmaAlunoEdicao");

            $combo.empty();
            $combo.append(
                $("<option>", {
                    value: "",
                    text: "Selecione..."
                })
            );

            response.turmas.forEach(function (turma) {

                $combo.append(
                    $("<option>", {
                        value: turma.id,
                        text: turma.nome
                    })
                );
            });

            $combo.val(String(aluno.turma_id));

            $("#btnSalvarEdicaoAluno").prop("disabled", false);

            bootstrap.Modal.getOrCreateInstance(
                document.getElementById("modalEditarRegistro")
            ).show();
        },

        error: function (xhr) {
            exibirMensagemSistema(
                xhr.responseJSON?.message ||
                "Não foi possível carregar os dados do aluno.",
                "danger"
            );
        }
    });
}


function salvarEdicaoAluno(idAluno) {

    const $botao = $("#btnSalvarEdicaoAluno");

    const nome = $("#nomeAlunoEdicao").val().trim();
    const turma_id = $("#turmaAlunoEdicao").val();

    if (!idAluno) {
        exibirMensagemSistema(
            "Não foi possível identificar o aluno.",
            "danger"
        );
        return;
    }

    if (!nome) {
        exibirMensagemSistema(
            "Informe o nome do aluno.",
            "warning"
        );

        $("#nomeAlunoEdicao").focus();
        return;
    }

    if (!turma_id) {
        exibirMensagemSistema(
            "Selecione uma turma.",
            "warning"
        );

        $("#turmaAlunoEdicao").focus();
        return;
    }

    $.ajax({
        type: "POST",
        url: `/alunos/${idAluno}/editar`,
        dataType: "json",

        data: {
            nome: nome,
            turma_id: turma_id
        },

        beforeSend: function () {

            $botao
                .prop("disabled", true)
                .html(`
                    <span class="spinner-border spinner-border-sm me-2"
                          aria-hidden="true"></span>
                    Salvando...
                `);
        },

        success: function (response) {

            if (!response.success) {
                exibirMensagemSistema(
                    response.message || "Não foi possível atualizar o aluno.",
                    "danger"
                );
                return;
            }

            $("#modalEditarRegistro").modal("hide");

            const aluno = response.aluno;

            // Atualiza a tabela sem recarregar a página
            const $linha = $(`#linhaAluno${aluno.id}`);

            $linha.find(".colNomeAluno").text(aluno.nome);
            $linha.find(".colTurmaAluno").text(aluno.turma);

            // Atualiza os atributos do botão de exclusão
            $linha.find(".btnExcluirAluno")
                .attr("nome-aluno", aluno.nome)
                .attr("matricula-aluno", aluno.matricula);

            // Fecha a modal
            const elementoModal = document.getElementById(
                "modalEditarRegistro"
            );

            if (elementoModal) {
                bootstrap.Modal.getOrCreateInstance(
                    elementoModal
                ).hide();
            }

            // Exibe mensagem de sucesso
            exibirMensagemSistema(
                response.message,
                "success"
            );
        },

        error: function (xhr) {

            const mensagem = xhr.responseJSON?.message
                || "Erro ao atualizar o aluno.";

            exibirMensagemSistema(
                mensagem,
                "danger"
            );
        },

        complete: function () {

            $botao
                .prop("disabled", false)
                .html(`
                    <i class="fa-solid fa-floppy-disk me-1"></i>
                    Salvar alterações
                `);
        }
    });
}



function enviarPerguntaIA() {

    const $input = $("#perguntaChatIA");
    const $botao = $("#btnEnviarPerguntaIA");

    const pergunta = $input.val().trim();

    if (!pergunta || $botao.prop("disabled")) {
        return;
    }

    adicionarMensagemChatIA("usuario", pergunta);

    $input.val("");

    $.ajax({
        type: "POST",
        url: "/api/ia/chat",
        dataType: "json",

        data: {
            pergunta: pergunta,
            conversa_id: conversaAtualIA || ""
        },

        beforeSend: function () {

            $botao.prop("disabled", true);

            mostrarDigitandoIA();
        },

        success: function (response) {

            $("#digitandoChatIA").remove();

            if (response.success) {

                // Guarda o ID da conversa criada ou recuperada
                conversaAtualIA = response.conversa_id;

                // Exibe a resposta da IA
                adicionarMensagemChatIA(
                    "ia",
                    response.resposta
                );

                // Atualiza a barra lateral após salvar a conversa
                carregarConversasIA();

            } else {

                exibirMensagemSistema(
                    response.message || "Não foi possível gerar a resposta.",
                    "danger"
                );
            }
        },

        error: function (xhr) {

            $("#digitandoChatIA").remove();

            exibirMensagemSistema(
                xhr.responseJSON?.message || "Erro ao comunicar com a IA.",
                "danger"
            );
        },

        complete: function () {

            $botao.prop("disabled", false);

            $input.trigger("focus");
        }
    });
}


function adicionarMensagemChatIA(tipo, mensagem) {

    const $historico = $("#historicoChatIA");

    $("#boasVindasChatIA").remove();

    const classeTipo = tipo === "usuario"
        ? "escolaia-chat-mensagem-usuario"
        : "escolaia-chat-mensagem-ia";

    const $mensagem = $("<div>", {
        class: `escolaia-chat-mensagem ${classeTipo}`
    });

    const $balao = $("<div>", {
        class: "escolaia-chat-balao"
    });

    if (tipo === "ia") {

        $balao.addClass("mensagem-ia-conteudo");

        const htmlSeguro = formatarRespostaIA(mensagem);

        if (htmlSeguro !== null) {

            $balao.html(htmlSeguro);

        } else {

            $balao.text(mensagem);

        }

    } else {

        // Mensagens do usuário continuam como texto puro
        $balao.text(mensagem);

    }

    $mensagem.append($balao);

    $historico.append($mensagem);

    rolarChatIA();
}


function rolarChatIA() {

    const historico = document.getElementById("historicoChatIA");

    if (historico) {
        historico.scrollTop = historico.scrollHeight;
    }
}


function mostrarDigitandoIA() {

    $("#digitandoChatIA").remove();

    const $digitando = $("<div>", {
        id: "digitandoChatIA",
        class: "escolaia-chat-mensagem escolaia-chat-mensagem-ia"
    });

    $digitando.append(`
        <div class="escolaia-chat-digitando">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `);

    $("#historicoChatIA").append($digitando);

    rolarChatIA();
}



function carregarConversasIA() {

    const $lista = $("#listaConversasIA");

    $lista.empty();

    $.ajax({
        type: "GET",
        url: "/api/ia/conversas",
        dataType: "json",

        beforeSend: function () {

            $lista.html(`
                <div class="text-center text-muted py-3">
                    <i class="fas fa-spinner fa-spin mr-2"></i>
                    Carregando conversas...
                </div>
            `);
        },

        success: function (response) {

            $lista.empty();

            if (!response.success) {
                $lista.text("Não foi possível carregar as conversas.");
                return;
            }

            if (!response.conversas.length) {

                $lista.html(`
                    <div class="text-muted small px-3 py-2">
                        Nenhuma conversa encontrada.
                    </div>
                `);

                return;
            }


            response.conversas.forEach(function (conversa) {

                const $item = $("<div>", {
                    class: "itemConversaIA"
                });

                const $botao = $("<button>", {
                    type: "button",
                    class: "btnConversaIA",
                    "data-conversa-id": conversa.id,
                    title: conversa.titulo
                });

                const $icone = $("<i>", {
                    class: "far fa-comment-dots"
                });

                const $titulo = $("<span>", {
                    class: "tituloConversaIA"
                }).text(conversa.titulo);

                $botao.append($icone, $titulo);

                const $excluir = $("<button>", {
                    type: "button",
                    class: "btnExcluirConversaIA",
                    "data-conversa-id": conversa.id,
                    title: "Excluir conversa",
                    "aria-label": "Excluir conversa"
                });

                $excluir.append(
                    $("<i>", {
                        class: "fa-solid fa-trash-can"
                    })
                );

                if (Number(conversaAtualIA) === Number(conversa.id)) {
                    $item.addClass("ativa");
                    $botao.addClass("ativa");
                }

                $item.append($botao, $excluir);

                $lista.append($item);
            });

        },

        error: function () {

            $lista.html(`
                <div class="text-danger small px-3 py-2">
                    Erro ao carregar conversas.
                </div>
            `);
        }
    });


}




function abrirConversaIA(conversaId) {

    const $historico = $("#historicoChatIA");

    $.ajax({
        type: "GET",
        url: `/api/ia/conversas/${conversaId}`,
        dataType: "json",

        beforeSend: function () {

            $historico.empty();

            $("#boasVindasChatIA").hide();

            $historico.html(`
                <div class="text-center text-muted py-4" id="loadingConversaIA">
                    <i class="fas fa-spinner fa-spin mr-2"></i>
                    Carregando conversa...
                </div>
            `);
        },

        success: function (response) {

            $("#loadingConversaIA").remove();

            if (!response.success) {

                exibirMensagemSistema(
                    response.message || "Não foi possível abrir a conversa.",
                    "danger"
                );

                return;
            }

            conversaAtualIA = response.conversa.id;

            $historico.empty();

            response.mensagens.forEach(function (mensagem) {

                const tipo = mensagem.papel === "user"
                    ? "usuario"
                    : "ia";

                adicionarMensagemChatIA(
                    tipo,
                    mensagem.conteudo
                );
            });

            $("#listaConversasIA .btnConversaIA")
                .removeClass("ativa")
                .filter(function () {
                    return Number($(this).attr("data-conversa-id")) === Number(conversaAtualIA);
                })
                .addClass("ativa");

            rolarChatIA();
        },

        error: function (xhr) {

            $("#loadingConversaIA").remove();

            exibirMensagemSistema(
                xhr.responseJSON?.message || "Erro ao carregar conversa.",
                "danger"
            );
        }
    });
}



function restaurarBoasVindasIA() {

    const $historico = $("#historicoChatIA");

    $historico.empty();

    if (boasVindasChatIA) {

        $historico.append(
            boasVindasChatIA.clone()
        );

        $("#boasVindasChatIA").show();
    }
}




function novaConversaIA() {

    // Não permite trocar de conversa durante uma resposta
    if ($("#btnEnviarPerguntaIA").prop("disabled")) {
        return;
    }

    // Desvincula a conversa anterior
    conversaAtualIA = null;

    // Restaura a tela inicial
    restaurarBoasVindasIA();

    // Remove a seleção da barra lateral
    $("#listaConversasIA .btnConversaIA")
        .removeClass("ativa");

    // Limpa e posiciona o cursor no campo
    $("#perguntaChatIA")
        .val("")
        .trigger("focus");
}




function excluirConversaIA(conversaId) {

    if ($("#btnEnviarPerguntaIA").prop("disabled")) {
        return;
    }

    if (!conversaId) {
        return;
    }

    const $botao = $(
        `.btnExcluirConversaIA[data-conversa-id="${conversaId}"]`
    );

    $.ajax({
        type: "DELETE",
        url: `/api/ia/conversas/${conversaId}`,
        dataType: "json",

        beforeSend: function () {
            $botao.prop("disabled", true);
        },

        success: function (response) {

            if (response.success) {

                // Só limpa o chat se a conversa excluída
                // for a que está aberta atualmente
                if (Number(conversaAtualIA) === Number(conversaId)) {
                    novaConversaIA();
                }

                $("#modalExcluirConversaIA").modal("hide");

                carregarConversasIA();

            } else {

                exibirMensagemSistema(
                    response.message || "Não foi possível excluir a conversa.",
                    "danger"
                );
            }
        },

        error: function (xhr) {

            exibirMensagemSistema(
                xhr.responseJSON?.message || "Erro ao excluir conversa.",
                "danger"
            );
        },

        complete: function () {
            $botao.prop("disabled", false);
        }
    });
}



function formatarRespostaIA(texto) {

    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
        return null;
    }

    const html = marked.parse(String(texto || ""), {
        gfm: true,
        breaks: false
    });

    return DOMPurify.sanitize(html);
}