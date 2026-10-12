$(document).ready(function () {
    iniciarTemporizadoresAlertas();

    if ($("#listaConversasIA").length) {
        carregarConversasIA();
    }

    if ($("#escolaIAChat").length) {

        boasVindasChatIA = $("#boasVindasChatIA").clone();

    }

    $('body').on('input', '#buscaAlunos', function () {
        filtrarAlunos($(this).val());
    });

    $('body').on('submit', '.formExcluirAluno', function (e) {
        if (!confirmarExclusaoAluno()) {
            e.preventDefault();
        }
    });



    $("body").on("click", ".btnExcluirAluno", function (e) {
        $("#modalConfirmarExclusaoAluno").modal('show');
        let idAluno = $(this).attr("id-aluno");
        let nomeAluno = $(this).attr("nome-aluno");
        let matriculaAluno = $(this).attr("matricula-aluno");

        $("#modalConfirmarExclusaoAluno").find("#nomeAlunoExclusao").text(`${nomeAluno} (${matriculaAluno})`);

        $("#modalConfirmarExclusaoAluno #btnConfirmarExclusaoAluno").attr('id-aluno', idAluno);


    });


    $("body").on("click", ".btnEditarAluno", function (e) {

        const idAluno = $(this).attr("id-aluno");

        if (idAluno) {
            carregarDadosEdicaoAluno(idAluno);
        }
    });

    $("body").on("click", "#btnSalvarEdicaoAluno", function () {
        let idAluno = $(this).attr("id-aluno");

        if (!idAluno) {
            return;
        }

        salvarEdicaoAluno(idAluno);

    });

    $("body").on("click", "#btnConfirmarExclusaoAluno", function () {
        let idAluno = $(this).attr("id-aluno");
        if (!idAluno) {
            return;
        }

        excluirAluno(idAluno);
    });


    $("body").on("click", "#btnEnviarPerguntaIA", function () {

        enviarPerguntaIA();

    });


    $("body").on("keydown", "#perguntaChatIA", function (e) {

        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {

            e.preventDefault();

            enviarPerguntaIA();
        }
    });


    $("body").on("click", ".btnConversaIA", function () {

        const conversaId = $(this).attr("data-conversa-id");

        if (!conversaId) {
            return;
        }

        abrirConversaIA(conversaId);
    });


    $("body").on("click", "#btnNovaConversaIA", function () {

        if ($("#btnEnviarPerguntaIA").prop("disabled")) {
            return;
        }

        novaConversaIA();
    });


    $("body").on("click", ".btnExcluirConversaIA", function (event) {

        $("#modalExcluirConversaIA").modal("show");
        let conversaId = $(this).attr("data-conversa-id");

        $("#btnConfirmarExclusaoIA").attr("id-conversa",conversaId);

        // event.preventDefault();
        // event.stopPropagation();

        // const conversaId = $(this).attr("data-conversa-id");

        // excluirConversaIA(conversaId);
    });

    $("body").on("click","#btnConfirmarExclusaoIA", function(){
        let conversaId = $(this).attr("id-conversa");
        excluirConversaIA(conversaId);

    });

})