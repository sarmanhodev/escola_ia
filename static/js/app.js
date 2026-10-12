$(document).on('input', '#buscaAlunos', function () { const termo = $(this).val().toLocaleLowerCase('pt-BR'); $('#tabelaAlunos tbody tr').each(function () { $(this).toggle($(this).text().toLocaleLowerCase('pt-BR').includes(termo)); }); });
$(document).on('submit', '.confirmar-exclusao', function (e) { if (!confirm('Excluir aluno e seus registros de notas e frequência?')) e.preventDefault(); });
