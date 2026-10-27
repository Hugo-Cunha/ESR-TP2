# Tipos de mensagem

Todas as mensagens de controlo são JSON, uma por linha, enviadas por **TCP**:

```json
{"tipo": "<TIPO>", "origem": "<IP de quem envia>", "dados": { ... }}
```

Os pacotes de **vídeo** vão por **UDP** e têm outro formato (ver o fim do ficheiro).

---

## REGISTO
Enviada pelo **nó** ao **bootstrapper** quando arranca (porta 5000). Não leva dados: o bootstrapper reconhece o nó pelo IP de origem da ligação.

```json
{"tipo": "REGISTO", "origem": "", "dados": {}}
```

## BOAS_VINDAS
Resposta do **bootstrapper**: o nome do nó no overlay e a lista dos seus vizinhos. A ligação fecha a seguir; o bootstrapper não volta a falar com este nó.

```json
{"tipo": "BOAS_VINDAS", "origem": "", "dados": {
    "ip": "10.0.19.21", "nome": "O3",
    "vizinhos": [{"ip": "10.0.18.20", "nome": "S1"}, {"ip": "10.0.17.20", "nome": "O2"}]
}}
```

## ERRO
Resposta do bootstrapper quando o IP não existe na configuração.

```json
{"tipo": "ERRO", "origem": "", "dados": {"motivo": "10.0.9.9 desconhecido"}}
```

---

## OLA
Primeira mensagem numa ligação TCP nova entre dois vizinhos (porta 6000). Quem tem o IP menor liga e envia primeiro; o outro responde com outro OLA.

```json
{"tipo": "OLA", "origem": "10.0.17.20", "dados": {"nome": "O2"}}
```

## ALIVE / ALIVE_RESP
Enviada de **1 em 1 s** a cada vizinho. O vizinho devolve o mesmo `t` num ALIVE_RESP e quem enviou calcula `RTT = agora - t`. Serve para duas coisas:
- **deteção de falhas**: se durante 3,5 s não chegar nada de um vizinho, ele é dado como morto;
- **métrica**: o RTT dá o atraso da ligação.

```json
{"tipo": "ALIVE",      "origem": "10.0.17.20", "dados": {"t": 1761569000.123}}
{"tipo": "ALIVE_RESP", "origem": "10.0.18.20", "dados": {"t": 1761569000.123}}
```

## ADEUS
Enviada a todos os vizinhos quando um nó sai de forma ordeira (comando `sair` ou Ctrl+C). Os vizinhos removem-no logo, sem esperar pelo timeout.

```json
{"tipo": "ADEUS", "origem": "10.0.17.20", "dados": {}}
```

---

## ANUNCIO
Enviada por cada **servidor** de 1 em 1 s e reenviada por todos os nós (inundação controlada). Constrói as tabelas de rotas.

```json
{"tipo": "ANUNCIO", "origem": "10.0.17.20", "dados": {
    "servidor": "10.0.18.20", "nome": "S1",
    "streams": ["filmeA", "filmeB"],
    "seq": 1761569000123,
    "custo": 1, "saltos": 1,
    "caminho": [["10.0.18.20", "S1"], ["10.0.17.20", "O2"]]
}}
```

| Campo | Significado |
|---|---|
| `seq` | hora do servidor em ms; identifica a ronda do anúncio (cada ronda só é reenviada uma vez) |
| `custo` | custo do caminho de quem envia até ao servidor (soma dos custos das ligações) |
| `saltos` | nº de ligações até ao servidor |
| `caminho` | nós por onde o anúncio passou; quem se encontrar na lista descarta-o (evita ciclos) |

Ao receber: `custo do candidato = custo + custo da ligação por onde chegou`. A **Origem** é o candidato de menor custo.

## ATIVAR
Enviada pelo nó que quer receber um fluxo à sua **Origem** para esse servidor. Quem recebe regista o remetente como **Destino** e, se ainda não recebia o fluxo, envia ATIVAR à sua própria Origem (e assim até ao servidor). É repetida de 2 em 2 s; um Destino que deixe de a repetir é removido ao fim de 6,5 s.

```json
{"tipo": "ATIVAR", "origem": "10.0.19.20", "dados": {"servidor": "10.0.18.20", "stream": "filmeA"}}
```

## DESATIVAR
"Já não preciso deste fluxo." Quem recebe remove o remetente dos Destinos; se ficar sem Destinos (e sem cliente local), envia DESATIVAR à sua Origem (**poda**).

```json
{"tipo": "DESATIVAR", "origem": "10.0.19.20", "dados": {"servidor": "10.0.18.20", "stream": "filmeA"}}
```

## PING
Teste do caminho (Etapa 3). Gerada pelo servidor (comando `ping`) e reenviada pelos Destinos de cada fluxo ativo. Cada nó escreve no log o caminho acumulado e acrescenta-se a ele.

```json
{"tipo": "PING", "origem": "10.0.17.20", "dados": {
    "servidor": "10.0.18.20", "stream": "filmeA", "t0": 1761569000.5,
    "caminho": ["S1", "O2"]
}}
```

---

## PEDIR / PEDIR_RESP / PARAR (cliente ↔ o seu onode, UDP porta 6003)
O cliente **não é nó do overlay**: só conhece o IP do seu onode. De 1 em 1 s envia PEDIR; o onode responde com o estado e envia-lhe o vídeo (porta UDP 6001 do cliente). Um cliente que não peça durante 3,5 s é esquecido. Se o onode morrer, o cliente fica sem vídeo mas continua a pedir; quando o onode volta, o vídeo volta.

```json
{"tipo": "PEDIR",      "origem": "", "dados": {"stream": "filmeB"}}
{"tipo": "PEDIR_RESP", "origem": "10.0.19.21", "dados": {"stream": "filmeB", "estado": "a enviar"}}
{"tipo": "PARAR",      "origem": "", "dados": {}}
```

O onode escolhe, entre os servidores que têm a stream, o de menor custo (se ele próprio for um servidor com a stream, é ele).

---

## Pacote de vídeo (UDP, porta 6001)

```
'O' 'T' | saltos (1 B) | servidor IPv4 (4 B) | t_envio (8 B) | len (1 B) | stream (len B) | pacote RTP
```

- O cabeçalho do overlay diz a que **fluxo** (servidor, stream) o pacote pertence. Um nó só o aceita se vier da sua Origem para esse servidor e envia uma cópia a cada Destino.
- O **pacote RTP** (12 B de cabeçalho + 1 frame JPEG) está explicado em `comum/RtpPacket.py`.
