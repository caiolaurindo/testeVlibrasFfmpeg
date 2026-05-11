# Conversor SRT para Libras (Video Generator)

Este projeto é uma ferramenta experimental que permite converter arquivos de legenda (SRT) em vídeos de tradução em Libras. Ele utiliza o **VLibras-Plugin** para renderizar um avatar 3D no navegador, captura os movimentos via Canvas e os converte em um arquivo MP4 usando **Python** e **FFmpeg**.

## 🚀 Como Funciona

1. **Frontend (HTML/JS):** Carrega o arquivo SRT, envia para o servidor para processamento de texto e sincroniza a sinalização do avatar do VLibras.
2. **Backend (Flask):** Recebe o texto original, "normaliza" para o formato de glossa (removendo ruídos e pontuação) e gerencia a conversão de vídeo.
3. **Conversão:** O navegador grava o elemento `<canvas>` em formato WebM. O servidor Python recebe esse arquivo e utiliza o FFmpeg para converter em MP4 (H.264) compatível com a maioria dos players.

## 🛠️ Pré-requisitos

Antes de começar, você precisará ter instalado em sua máquina:

- **Python 3.x**
- **FFmpeg** (Essencial para a conversão de vídeo).
  - *Dica:* Certifique-se de que o comando `ffmpeg` está acessível no seu PATH (terminal).

## 📥 Instalação

1. **Clone o repositório ou baixe os arquivos.**
2. **Instale as dependências do Python:**
   Abra o terminal na pasta do projeto e execute:

```bash
pip install -r requirements.txt
```

*As dependências incluem: `flask`, `flask-cors` e `pysrt`.*

## ⚡ Como Usar

### 1. Inicie o Servidor Backend

No terminal, execute o script do servidor:

```bash
python server.py
```

O servidor ficará rodando em `http://localhost:5000`.

### 2. Abra a Interface

Abra o arquivo `index.html` em seu navegador (Chrome ou Edge são recomendados para melhor suporte à captura de canvas).

### 3. Processo de Geração

#### Carregar SRT

Clique em `"📁 Carregar SRT"` e selecione seu arquivo de legenda. O status mudará para `"Legendas carregadas e prontas!"`.

#### Aguarde o Avatar

Espere o boneco do VLibras aparecer no canto da tela.

#### Gerar e Gravar

Clique em `"⏺ Gerar e Gravar"`.

- O sistema começará a percorrer as legendas.
- O avatar sinalizará automaticamente conforme o tempo definido no SRT.
- O canvas está sendo gravado em tempo real.

#### Conversão Automática

Ao finalizar a última legenda, a gravação para e o vídeo é enviado ao servidor.

#### Download

Quando o status indicar `"Conversão concluída!"`, um link `"⬇ Baixar Vídeo MP4"` aparecerá.

## 📂 Estrutura de Arquivos

- `index.html`: Interface do usuário e lógica de captura de mídia.
- `server.py`: Servidor Flask que processa glossas e executa o FFmpeg.
- `requirements.txt`: Lista de bibliotecas Python necessárias.
- `/media`: Pasta criada automaticamente onde os vídeos gerados são salvos com timestamp.

## ⚠️ Observações Importantes

### FFmpeg no Windows

Se o script não encontrar o FFmpeg, verifique se ele foi instalado corretamente e adicionado às variáveis de ambiente do sistema.

### Foco da Aba

Para garantir a gravação correta, mantenha a aba do navegador visível e ativa durante o processo de gravação.

## Resumo Técnico do Repositório

- **Backend:** Utiliza `Flask` com suporte a `CORS` para comunicação com o frontend. O método `parse_srt` extrai os tempos e textos das legendas, enquanto a função `normalizar` limpa o texto para o padrão de sinalização (Uppercase, sem ruídos como "hmm", "ah").
- **Processamento de Vídeo:** O `subprocess.run` no Python invoca o FFmpeg com o codec `libx264` e o preset `ultrafast` para garantir agilidade na conversão.
- **Sincronização:** No frontend, a função `playSincronizado()` utiliza `setTimeout` baseados nos milissegundos convertidos do formato SRT para acionar o comando `window.plugin.player.translate(item.glossa)`.
