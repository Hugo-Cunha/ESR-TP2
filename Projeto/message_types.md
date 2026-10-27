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
- **métrica**: o RTT/2 é o atraso da ligação (componente A do custo; ver README, secção 4).

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
Enviada por cada **servidor** a cada segundo e reenviada pelos onodes (inundação controlada). Constrói as tabelas de rotas. **Não transporta o caminho**: cada onode fica a saber apenas por que vizinho chega ao servidor e com que custo.

```json
{"tipo": "ANUNCIO", "origem": "10.0.17.20", "dados": {
    "servidor": "10.0.18.20", "nome": "S1",
    "streams": ["filmeA", "filmeB"],
    "seq": 1761569000123,
    "custo": 1, "saltos": 1
}}
```

| Campo | Significado |
|---|---|
| `seq` | número de sequência gerado pelo servidor (hora em ms); identifica a ronda e garante que informação antiga nunca se sobrepõe à recente |
| `custo` | custo de quem envia até ao servidor (soma dos custos das ligações; ver README, secção 4). **`null` = custo infinito** (*route poisoning*: quem envia perdeu a rota) |
| `saltos` | número de ligações até ao servidor (usado em desempates e na tabela) |

Regras de processamento:
- custo do candidato = `custo` + custo da ligação por onde o anúncio chegou;
- a **Origem** é o candidato **viável** de menor custo. É viável se `seq` for mais recente do que o conhecido, ou se, com o mesmo `seq`, o `custo` anunciado for estritamente inferior ao melhor custo já obtido (condição de viabilidade do Babel/EIGRP);
- cada ronda (`seq`) é reenviada uma única vez (ou de novo, se o custo melhorar), **a todos os vizinhos exceto a Origem** (*split horizon*);
- quem fica sem candidato viável envia de imediato um ANUNCIO com `custo: null` a todos os vizinhos.

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
'O' 'T' | saltos (1 B) | seq_ligacao (4 B) | servidor IPv4 (4 B) | t_envio (8 B) | len (1 B) | stream (len B) | pacote RTP
```

| Campo | Significado |
|---|---|
| `saltos` | número de onodes atravessados (cada um soma 1) |
| `seq_ligacao` | número de sequência **por ligação**: quem envia numera os pacotes que envia a cada vizinho; quem recebe conta as lacunas e obtém as perdas dessa ligação (medição passiva usada na métrica) |
| `servidor`, `stream` | identificam o **fluxo**; um onode só aceita o pacote se vier da sua Origem para esse servidor e envia uma cópia a cada Destino e a cada cliente |
| `t_envio` | instante de emissão no servidor; o cliente calcula o atraso fim-a-fim |

O **pacote RTP** (12 B de cabeçalho + 1 *frame* JPEG) está descrito campo a campo em `comum/RtpPacket.py`.
