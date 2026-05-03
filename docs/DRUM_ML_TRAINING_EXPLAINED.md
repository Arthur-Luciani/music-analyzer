# 🧠 Como treinar uma IA para classificar peças de bateria

> Explicação prática, sem jargões, respondendo: **o que é, como funciona, dá pra fazer em casa, e vale a pena?**

---

## A ideia em uma frase

Queremos ensinar o computador a ouvir um golpe de bateria e dizer: *"isso é um kick"*, *"isso é uma caixa"*, *"isso é um hi-hat"* — **sem que a gente precise escrever as regras manualmente**.

---

## 1. Por que considerar isso?

Na proposta do `music-analyzer`, a **Fase 2** classifica cada golpe usando **regras fixas por frequência**:

```
"Se tem muita energia no grave → é kick"
"Se tem muita energia no agudo → é hi-hat"
```

Isso funciona razoavelmente (~70-80%), mas tem limitações:
- **Toms graves** podem ser confundidos com **kicks**
- **Rimshots** (batidas na borda da caixa) soam agudos e podem ser confundidos com **hi-hat**
- Cada estilo de bateria/gênero musical soa diferente

A alternativa é: **em vez de escrever as regras, deixar o computador aprender sozinho com exemplos**.

---

## 2. Como funciona o processo — passo a passo

### Passo 1: Juntar exemplos (o "dataset")

Precisamos de **centenas de sons** organizados em pastas:

```
dataset/
├── kick/        ← 300+ arquivos .wav de kicks diferentes
├── snare/       ← 300+ arquivos .wav de caixas diferentes
├── hihat/       ← 300+ arquivos .wav de hi-hats diferentes
├── tom/         ← 200+ arquivos .wav de toms diferentes
└── cymbal/      ← 200+ arquivos .wav de pratos diferentes
```

**De onde vêm esses sons?**

| Fonte | O que é | Custo |
|---|---|---|
| **IDMT-SMT-Drums** | Dataset acadêmico com 608 arquivos de kick, snare e hi-hat anotados profissionalmente | Gratuito (Zenodo) |
| **ENST-Drums** | Gravações de 3 bateristas profissionais com kits diferentes, multi-track | Gratuito (Zenodo) |
| **Sample packs** | Pacotes de sons de bateria usados por produtores musicais (um bom produtor tem milhares) | Muitos gratuitos |
| **Nosso próprio app** | Podemos recortar os golpes detectados na Fase 2 e ir classificando manualmente para construir um dataset personalizado | Gratuito (mas dá trabalho) |

> [!TIP]
> O mais legal: podemos começar com datasets acadêmicos prontos e, com o tempo, **o próprio uso do app pode gerar dados de treinamento** — se adicionarmos uma feature onde o usuário corrige a classificação errada ("isso não é um tom, é um snare"), cada correção vira um exemplo novo para o modelo.

### Passo 2: Transformar som em "imagem" (espectrograma)

O computador não entende áudio diretamente. Precisamos transformar cada som em algo que ele consiga analisar visualmente.

Um **espectrograma mel** é como uma "radiografia" do som:
- Eixo horizontal = tempo
- Eixo vertical = frequência (grave embaixo, agudo em cima)
- Cor/brilho = intensidade

```
Kick:                    Snare:                  Hi-Hat:
████████                 ██░░████                ░░░░░░██
████████                 ██░░████                ░░░░████
████░░░░                 ████████                ░░██████
████░░░░                 ████░░░░                ████████
(energia no grave)       (energia espalhada)     (energia no agudo)
```

Cada golpe de ~50ms vira uma "imagem" de 64x64 ou 128x128 pixels.

### Passo 3: Treinar o modelo

O "treinamento" é um processo repetitivo:

```
Repetir 50-100 vezes (chamadas "épocas"):
  1. Pegar um lote de 32 espectrogramas
  2. Mostrar ao modelo e perguntar: "o que é isso?"
  3. O modelo chuta: "kick" (ele começa errando muito)
  4. Comparar com a resposta correta
  5. Ajustar os parâmetros internos para errar menos na próxima vez
```

É como flashcards: você mostra a imagem, ele tenta responder, e com a repetição vai acertando mais.

### Passo 4: Usar o modelo treinado

Depois de treinado, o modelo vira um **arquivo** (~5-20 MB) que:
1. Recebe um espectrograma de um golpe de bateria
2. Responde em milissegundos: `{ "kick": 92%, "snare": 5%, "tom": 3% }`

---

## 3. Dá pra fazer em casa? Sim!

### O que você precisa

| Requisito | O que é | Você tem? |
|---|---|---|
| **GPU** | Placa de vídeo NVIDIA com CUDA (GTX 1060+ ou RTX) | ✅ Você já usa GPU pro Demucs |
| **PyTorch** | Biblioteca Python para treinar modelos | ✅ Já está no `requirements.pipeline.txt` |
| **Dataset** | Sons organizados por categoria | 🟡 Precisa baixar/montar |
| **Conhecimento** | Entender o código de treinamento | 📄 É um script de ~150 linhas |

### Quanto tempo demora?

| Etapa | Tempo estimado |
|---|---|
| Baixar e preparar dataset | 2-4 horas |
| Escrever script de treinamento | 4-8 horas (com referência) |
| **Treinar o modelo** (na GPU) | **5-30 minutos** ← é rápido! |
| Testar e ajustar | 2-4 horas |
| Integrar no app | 4-8 horas |
| **Total** | **~2-4 dias de trabalho** |

> [!IMPORTANT]
> O treinamento em si é **muito rápido** para esse tipo de problema — estamos falando de minutos, não horas ou dias. O que leva tempo é preparar os dados e integrar no app. A parte mais cara computacionalmente (Demucs) já roda na sua máquina.

### Código seria algo assim (simplificado)

```python
import torch
import torchaudio
from torch import nn

# 1. Definir o modelo (rede neural)
class DrumClassifier(nn.Module):
    def __init__(self, num_classes=5):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),   # "olha" padrões pequenos
            nn.ReLU(),                         # ativa os neurônios
            nn.MaxPool2d(2),                   # reduz o tamanho
            nn.Conv2d(16, 32, 3, padding=1),   # padrões maiores
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Flatten(),                      # achata pra uma lista
            nn.Linear(32 * 16 * 16, 64),       # conecta tudo
            nn.ReLU(),
            nn.Linear(64, num_classes),        # 5 saídas: kick, snare, hihat, tom, cymbal
        )
    
    def forward(self, x):
        return self.layers(x)

# 2. Carregar dados (espectrogramas organizados em pastas)
# dataset/kick/*.wav, dataset/snare/*.wav, etc.

# 3. Treinar
model = DrumClassifier(num_classes=5)
model = model.to("cuda")  # usar GPU

for epoca in range(50):
    for lote_espectrogramas, respostas_corretas in dataloader:
        predicao = model(lote_espectrogramas.to("cuda"))
        erro = loss_fn(predicao, respostas_corretas.to("cuda"))
        erro.backward()       # calcular correções
        optimizer.step()      # aplicar correções

# 4. Salvar modelo treinado (~10 MB)
torch.save(model.state_dict(), "drum_classifier.pth")
```

### Usando no app (depois de treinado)

```python
# Na análise de bateria, para cada golpe detectado:
model = DrumClassifier()
model.load_state_dict(torch.load("drum_classifier.pth"))

espectrograma = gerar_espectrograma(golpe_audio)
resultado = model(espectrograma)
# resultado = {"kick": 0.92, "snare": 0.05, "hihat": 0.02, "tom": 0.01}
classe = "kick"  # maior probabilidade
```

---

## 4. Nível de complexidade — honestamente

| Aspecto | Dificuldade | Comentário |
|---|---|---|
| Entender o conceito | 🟢 Fácil | É "mostrar exemplos e ele aprende" |
| Preparar o dataset | 🟡 Médio | Organizar arquivos, garantir qualidade, balancear quantidade por classe |
| Escrever o código de treinamento | 🟡 Médio | ~150 linhas de Python com PyTorch; muitos tutoriais disponíveis |
| Rodar o treinamento | 🟢 Fácil | Um comando, espera 10-30 min |
| Ajustar pra ficar bom | 🟡 Médio | Experimentar parâmetros, analisar erros, melhorar dados |
| Integrar no pipeline do app | 🟢 Fácil | Substituir a função `classify_hit()` por uma chamada ao modelo |
| **Complexidade geral** | **🟡 Médio** | Factível em casa, especialmente porque já temos PyTorch e GPU |

---

## 5. Vale a pena? Comparação das abordagens

| | Regras por frequência (Fase 2) | IA treinada (futuro) |
|---|---|---|
| **Acurácia esperada** | ~70-80% (kicks e hi-hats bons, toms/snare confundem) | ~90-95% com bom dataset |
| **Tempo para implementar** | 5-8 dias | +2-4 dias sobre a Fase 2 |
| **Manutenção** | Ajustar thresholds manualmente | Retreinar com mais dados |
| **Adaptabilidade** | Fraca (mesmas regras pra tudo) | Forte (aprende com novos exemplos) |
| **Depende de GPU** | Não | Sim para treinar, não para usar |
| **Complexidade** | Baixa | Média |

---

## 6. Recomendação prática

```
Fase 2 (AGORA)     → Implementar com regras por frequência
                      Funciona, é simples, resolve 80% dos casos

Fase 2.5 (DEPOIS)  → Treinar modelo com dataset acadêmico
                      Melhora precisão para ~90-95%
                      Pode ser feito incrementalmente

Fase 2.9 (FUTURO)  → Feedback loop com usuários
                      Cada correção do usuário melhora o modelo
                      O app fica mais inteligente com o uso
```

> [!NOTE]
> **Resumo**: Sim, dá pra fazer em casa. Não é trivial, mas também não é ciência de foguete. O hardware que você já tem (GPU + PyTorch) é exatamente o que se precisa. A recomendação é **começar com regras simples** na Fase 2 e **evoluir para IA** depois, quando o app já estiver gerando dados que podem alimentar o treinamento.
