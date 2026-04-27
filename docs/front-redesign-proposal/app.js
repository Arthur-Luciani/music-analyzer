(function () {
  var page = document.body.getAttribute('data-page') || '';

  var links = document.querySelectorAll('.nav-links a[data-page-link]');
  links.forEach(function (link) {
    if (link.getAttribute('data-page-link') === page) {
      link.classList.add('active');
    }
  });

  if (page === 'session') {
    runProgressDemo();
  }

  if (page === 'workspace') {
    bindMixer();
  }
})();

function runProgressDemo() {
  var rail = document.querySelector('[data-progress-fill]');
  var valueNode = document.querySelector('[data-progress-value]');
  var messageNode = document.querySelector('[data-progress-message]');
  if (!rail || !valueNode || !messageNode) {
    return;
  }

  var progress = 92;
  var messages = [
    'Baixando audio em alta qualidade',
    'Separando stems no modelo htdemucs',
    'Finalizando arquivos para exportacao',
    'Sessao pronta para mix e download'
  ];
  var idx = 1;

  rail.style.width = progress + '%';
  valueNode.textContent = progress + '%';

  var timer = setInterval(function () {
    if (progress >= 100) {
      clearInterval(timer);
      messageNode.textContent = messages[messages.length - 1];
      return;
    }

    progress = Math.min(progress + 2, 100);
    idx = Math.min(idx + 1, messages.length - 1);

    rail.style.width = progress + '%';
    valueNode.textContent = progress + '%';
    messageNode.textContent = messages[idx];
  }, 1100);
}

function bindMixer() {
  var sliders = document.querySelectorAll('[data-mix-slider]');
  sliders.forEach(function (slider) {
    var target = document.querySelector('[data-mix-value="' + slider.name + '"]');
    if (!target) {
      return;
    }

    target.textContent = slider.value + '%';
    slider.addEventListener('input', function () {
      target.textContent = slider.value + '%';
    });
  });

  var master = document.querySelector('[data-master-slider]');
  var masterTarget = document.querySelector('[data-master-value]');
  if (master && masterTarget) {
    masterTarget.textContent = master.value + '%';
    master.addEventListener('input', function () {
      masterTarget.textContent = master.value + '%';
    });
  }
}
