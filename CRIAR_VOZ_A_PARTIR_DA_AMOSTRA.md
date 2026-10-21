# Cadastrar a voz do V a partir da amostra

Escolha um arquivo de áudio que você tenha autorização para usar. Informe o
caminho para a amostra ao executar o script.

O projeto já tem o cadastro preparado, mas não havia uma chave ElevenLabs disponível nesta máquina. A chave nunca deve ser enviada no chat.

1. Abra um terminal na pasta do V.
2. Execute `python configurar_elevenlabs.py` e cole a chave quando o terminal pedir. O arquivo é protegido pelo Windows quando o DPAPI está disponível.
3. Execute `python cadastrar_voz_v.py "C:\caminho\para\sua-amostra.mp3"`.
4. Se o cadastro for aceito, o novo `voice_id` será salvo em `config/default.json` com o perfil `V Prime`.
5. Reabra o V e use **Voz e tarefas → Voz → Salvar e ouvir**.

Se o provedor recusar a amostra, a configuração anterior permanece intacta. O cadastro depende da conta, do plano e das regras do provedor. A amostra precisa ser autorizada para clonagem.
