# Visão e câmera no V

## Como usar

Abra **Câmera** no topo da interface Orbital ou na barra de ferramentas da interface principal. Escolha a webcam e clique em **Ligar câmera**. A câmera começa desligada e fecha quando você fecha a janela, sai do V ou troca a interface.

Com a voz contínua habilitada, diga:

- **V, ligue a câmera.**
- **V, o que você está vendo?** — responde com os objetos da imagem atual.
- **V, você está me vendo?** — verifica a presença de pessoas; não identifica quem são.
- **V, descreva a imagem.** — análise opcional com Gemini.
- **V, leia o texto da câmera.** — leitura visual opcional com Gemini, sujeita a erros.
- **V, desligue a câmera.**

Para perguntas detalhadas, marque **Permitir enviar uma foto ao Gemini quando eu pedir uma análise**. Escreva a pergunta na janela e clique em **Analisar foto com Gemini**. É necessário ter o Gemini habilitado e configurado no V. A autorização é desmarcada ao fechar a janela. Desligar a câmera descarta respostas pendentes, mas não recolhe uma imagem que já foi enviada.

## Funcionamento

A captura usa Qt Multimedia, já incluído no aplicativo. YOLOX Nano reconhece 80 categorias COCO, incluindo pessoa, celular, copo, notebook, teclado e animais. O modelo de 3,66 MB fica em `models/vision/yolox_nano.onnx`, com licença Apache 2.0 e origem/hash registrados ao lado. O aplicativo verifica o hash antes de carregá-lo.

A detecção roda com ONNX Runtime na CPU e duas threads, preservando a GPU para o reconhecimento de voz. Há um único trabalho de análise por vez, sem fila de fotos. A prévia usa vídeo nativo do Qt e é independente da análise. Os objetos identificados aparecem em texto abaixo do vídeo; uma foto antiga com caixas não substitui mais a imagem ao vivo. A captura prefere 640 × 480 com pelo menos 24 quadros/s, conforme os formatos disponíveis na câmera. A conversão dos frames para análise ocorre na thread de processamento. Cada ciclo aguarda pelo menos 700 ms e aumenta o intervalo em máquinas mais lentas, sem formar fila de imagens. Resultados de uma sessão anterior são descartados.

As imagens da câmera ficam apenas na memória: não há gravação de vídeo ou salvamento automático de fotos. A análise local não usa internet. Somente um pedido online, com a opção de envio marcada, envia uma imagem JPEG ao Gemini. O serviço pode cobrar conforme a chave/cota e trata os dados conforme seus termos. As descrições não executam comandos do computador.

Nenhum reconhecimento facial de identidade foi implementado. A detecção de uma pessoa não comprova sua identidade. Também não inferimos humor por imagem. Objetos fora das 80 categorias, ambientes escuros, reflexos e objetos pequenos podem gerar erros. O Gemini amplia as descrições, mas também pode errar.

## Pesquisa e decisões

- [Qt QCamera](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QCamera.html) e [QVideoSink](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QVideoSink.html): captura e acesso aos frames sem instalar outro sistema de câmera.
- [YOLOX / ONNX Runtime](https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime): modelo Nano oficial, pré-processamento BGR, entrada 416 × 416 e decodificação dos resultados.
- [YOLOX / licença](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE): Apache 2.0. Evita adicionar um framework de treinamento ao aplicativo.
- [Gemini / compreensão de imagens](https://ai.google.dev/gemini-api/docs/image-understanding): perguntas sobre uma imagem enviada sob demanda, usando o modelo já configurado no V.
- [Gemini / termos](https://ai.google.dev/gemini-api/terms): tratamento dos dados varia por modalidade e região; consulte os termos da sua conta antes de enviar imagens pessoais.
- [MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python): pontos e movimentos faciais são diferentes de reconhecimento de identidade. Não é necessário para esta primeira integração.

## Verificação

A imagem pública `assets/dog.jpg` do repositório oficial YOLOX foi usada no teste local. O modelo detectou cachorro (83%), carro (81%) e bicicleta (81%). Nesta máquina, três execuções levaram aproximadamente 258 ms, 32 ms e 30 ms; isso mede apenas a inferência/processamento local dessa imagem, não a latência da webcam nem a precisão geral.

Testes automatizados cobrem decodificação e supressão de caixas duplicadas, comandos e negações, imagem antiga, câmera ausente/desconectada, encerramento com análise pendente, falha do modelo e envio online desabilitado. A verificação automatizada não substitui testar a webcam real, iluminação e áudio do usuário. A chamada real ao Gemini exige a opção de envio na interface.

Validação em 01/10/2026: 91 testes passaram, incluindo visão, reconhecimento de voz, controles de fala e resumo diário. A prévia visual e o encaminhamento dos comandos foram verificados sem ativar a webcam, usando a imagem pública de referência. Nenhuma foto do usuário foi capturada ou enviada para esse teste.

Se a câmera não abrir, selecione outra fonte, feche aplicativos que a estejam usando e confira **Configurações do Windows → Privacidade e segurança → Câmera → Permitir que aplicativos da área de trabalho acessem a câmera**. iVCam/Iriun só funcionam quando o respectivo aplicativo está conectado; uma webcam USB evita essa dependência do telefone.

## Correção de fluidez — 01/10/2026

A versão anterior interrompia a atualização contínua da prévia depois da primeira detecção. A prévia passava a depender de cada resultado de reconhecimento, causando a aparência de travamento. A nova versão usa QVideoWidget para vídeo contínuo, guarda apenas o frame mais recente e converte imagens fora da interface. O painel mostra a taxa de captura e o tempo da última análise local para facilitar o diagnóstico de problemas de câmera ou desempenho.

Os testes incluem uma análise deliberadamente pendente enquanto novos frames chegam, garantia de que resultados antigos não substituam o vídeo, seleção de formato e redução automática da frequência de análise.

Após a correção, passaram 56 testes de visão e voz. Um teste contínuo de 12 segundos injetou 248 frames sintéticos no QVideoSink enquanto o detector real realizou 13 análises. O fluxo permaneceu ativo e o frame final estava atualizado. O temporizador de interface teve intervalo de até 10,5 ms em 95% das amostras, com pico de 358,5 ms durante o teste incluindo inicialização. Isso verifica o processamento e a interface, não o driver ou a taxa de quadros da webcam real. O resultado está em `logs/vision/fluency_check.json`; o teste pode ser repetido com `python -m tests.benchmark_vision_preview` no ambiente do projeto.
