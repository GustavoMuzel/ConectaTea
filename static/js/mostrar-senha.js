// Botão "Mostrar" ao lado de cada campo de senha (login, cadastro e troca de senha).
// Ver o que foi digitado evita erro de digitação, sem depender de lembrar o que se digitou às cegas.
// Sem ícone nem animação: só texto, como o resto da interface de baixa carga sensorial.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('input[type="password"]').forEach(function (campo) {
    var grupo = document.createElement('div');
    grupo.className = 'input-group';
    campo.parentNode.insertBefore(grupo, campo);
    grupo.appendChild(campo);

    var botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'btn btn-outline-secondary botao-mostrar-senha';
    botao.setAttribute('aria-controls', campo.id);
    botao.setAttribute('aria-pressed', 'false');
    var texto = document.createElement('span');
    texto.textContent = 'Mostrar';
    var complemento = document.createElement('span');
    complemento.className = 'visually-hidden';
    complemento.textContent = ' a senha';
    botao.append(texto, complemento);
    grupo.appendChild(botao);

    botao.addEventListener('click', function () {
      var mostrar = campo.type === 'password';
      campo.type = mostrar ? 'text' : 'password';
      texto.textContent = mostrar ? 'Esconder' : 'Mostrar';
      botao.setAttribute('aria-pressed', String(mostrar));
      campo.focus();
    });

    // Ao enviar, a senha volta a ficar escondida (o navegador não guarda o texto como campo comum).
    if (campo.form) {
      campo.form.addEventListener('submit', function () { campo.type = 'password'; });
    }
  });
});
