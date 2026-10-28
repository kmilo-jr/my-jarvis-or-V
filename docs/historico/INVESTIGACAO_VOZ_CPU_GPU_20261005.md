# Investigação: usar CPU e GPU na voz Qwen

## Resultado

O runtime instalado possui três preferências explícitas: `auto`, `cpu` e `cuda`. A DLL expõe `qwen3_tts_set_backend_preference`; a configuração do V já usa essa função. Não existe na API local um parâmetro de camadas, porcentagem de offload ou divisão fixa entre CPU e CUDA.

## O que “híbrido” significa neste runtime

Quando o backend principal é CUDA, o código nativo cria também um backend CPU e um `ggml_backend_sched`. Isso permite ao scheduler usar CPU como fallback para operações que não podem executar no dispositivo principal. O carregamento e o agendamento continuam partindo de um backend principal; isso não é uma divisão controlada do modelo nem garante que a carga de GPU caia de forma previsível.

O decodificador de áudio também possui um scheduler e, no modo de áudio em blocos, um decodificador separado. Em teoria isso abre uma combinação entre etapas, mas a API Python/C atual não permite escolher o backend do transformador e do decodificador independentemente. Para obter esse modo seria necessário alterar e recompilar a DLL, expor novas funções C e medir sincronização, memória e lacunas de áudio.

## O que foi confirmado

- A DLL instalada exporta a função de streaming ICL.
- O backend CPU confirmou geração de áudio em quatro execuções de teste.
- O scheduler nativo é criado com backend principal e CPU fallback quando o principal é acelerado.
- Não há controle existente de `gpu_layers`, `offload` ou percentuais CPU/GPU.
- A documentação pública do projeto descreve seleção `auto`, `cuda` ou `cpu` e fallback; não descreve offload parcial configurável. [Repositório qwen3-tts.cpp](https://github.com/Danmoreng/qwen3-tts.cpp)

## Decisão para o V

Manter CPU com oito threads é a configuração atual porque removeu a saturação de GPU percebida durante o vídeo. Um híbrido recompilado pode ser uma segunda etapa, mas precisa de um benchmark real com vídeo e voz simultâneos. Ativar `auto` agora devolveria o processamento à GPU e poderia recriar o problema.

## Próxima experiência segura

Se for implementado, o teste deve comparar três processos separados: CPU, CUDA e híbrido experimental. Cada um precisa registrar backend confirmado, tempo até primeiro áudio, tempo de geração, uso de GPU, memória, falhas de buffer e quadros perdidos no vídeo. Sem essa comparação, “usar os dois” seria apenas uma suposição.
