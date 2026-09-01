# 🏭 Protótipo de Gêmeo Digital Industrial (Digital Twin)

Este projeto implementa o **Gêmeo Digital (Digital Twin)** da linha de triagem de caixas por altura (*Sorting by Height*), baseado na arquitetura de 3 camadas da norma **ISO 23247** e nos princípios de governança e sanitização de dados da norma **ISO/IEC 30173:2025**.

---

## 🏛️ Estrutura de Pastas do Projeto

```text
prototipo/
│
├── factoryio/                      # 📁 1. Camada do Ativo Físico e Automação
│   ├── SortingByHeight_Basic.project  # Lógica Ladder desenvolvida no CODESYS
│   ├── SortingByHeight_Basic.xml      # Mapa de símbolos OPC UA
│   ├── index.html                     # Documentação das tags da cena
│   └── monitoramentoOPCUA.py          # Script original do colega
│
├── gemeo-digital/                  # 📁 2. Camada do Núcleo do Gêmeo Digital (Python)
│   ├── config.py                      # Parâmetros de temporização e nós OPC UA
│   ├── data_sanitizer.py              # Sanitização (Debouncing 50ms, qualidade e linhagem ISO 30173)
│   ├── petri_engine.py                # Motor da Rede de Petri & Detecção de Anomalias (Stuck ON/OFF, Timeout)
│   ├── aas_model.py                   # Modelo de Casca Administrativa (Asset Administration Shell - BaSyx)
│   └── opc_connector.py               # Conector OPC UA assíncrono bidirecional (asyncua)
│
├── dashboard/                      # 📁 3. Camada de Aplicação do Usuário / Supervisório
│   └── app.py                         # Interface Web em Streamlit com painel ao vivo e injeção de falhas
│
├── docs/                           # 📚 Documentações Técnicas e Especificações
│   ├── ARQUITETURA.md              # Documentação técnica completa da arquitetura
│   ├── ARQUITETURA.pdf             # PDF formatado para entrega e apresentação
│   └── img/                        # Diagramas em alta resolução (300 DPI)
│
├── Dockerfile                      # Empacotamento Docker da aplicação
├── docker-compose.yml              # Orquestração com Hot-Reloading de volumes
└── requirements.txt                # Dependências Python
```

---

## ⚙️ Pré-requisitos (Ativo Físico & Automação)

Antes de iniciar o Gêmeo Digital (seja com ou sem Docker), certifique-se de que a automação física está pronta:

1. **CODESYS Control Win V3 x64:**
   * Abra o projeto `prototipo/factoryio/SortingByHeight_Basic.project` no CODESYS.
   * Realize o **Login** e coloque o CLP no modo **`RUN`** (símbolo de Play verde no CODESYS).
   * O servidor OPC UA estará escutando na porta padrão `opc.tcp://127.0.0.1:4840`.
2. **Factory I/O:**
   * Abra a cena correspondente (*Sorting by Height - Basic*).
   * Em *File $\rightarrow$ Drivers*, confirme que o driver OPC UA está conectado (ícone verde).
   * Pressione o botão **Play (▶️)** no topo da janela do Factory I/O.

---

## 🚀 Como Executar o Gêmeo Digital

Você pode executar a aplicação de duas maneiras:

---

### Opção 1: Executando SEM Docker (Python Local) 🐍

Se você já possui Python 3.10+ instalado no seu computador:

1. Abra o terminal e navegue até a pasta `prototipo`:
   ```powershell
   cd prototipo
   ```

2. Instale as dependências necessárias:
   ```powershell
   pip install -r requirements.txt
   ```

3. Inicie o Dashboard Supervisório:
   ```powershell
   streamlit run dashboard/app.py
   ```

4. O Streamlit abrirá automaticamente no seu navegador no endereço:  
   👉 **`http://localhost:8501`**

---

### Opção 2: Executando COM Docker (Docker Compose) 🐳

Ideal para isolamento total de ambiente ou execução em outras máquinas sem precisar instalar Python manualmente.

1. Abra o terminal na pasta `prototipo`:
   ```powershell
   cd prototipo
   ```

2. Suba o container com o Docker Compose:
   ```powershell
   docker compose up
   ```
   *(Caso seja a primeira vez ou tenha adicionado novas bibliotecas no `requirements.txt`, use `docker compose up --build`)*.

3. Abra o navegador em:  
   👉 **`http://localhost:8501`**

> 💡 **Nota de Desenvolvimento (Live Reload):** O `docker-compose.yml` está configurado com mapeamento de volumes. Qualquer alteração que você fizer e salvar nos arquivos Python (`app.py`, `petri_engine.py`, etc.) no seu editor será refletida **imediatamente** no container sem precisar recompilar a imagem!

#### Comandos Úteis do Docker:
* **Executar em segundo plano (background/daemon):**
  ```powershell
  docker compose up -d
  ```
* **Visualizar logs em tempo real:**
  ```powershell
  docker compose logs -f
  ```
* **Parar a aplicação:**
  ```powershell
  docker compose down
  ```

---

## 🔍 Funcionalidades do Gêmeo Digital

1. **Sanitização de Dados Industriais (ISO/IEC 30173:2025):**
   * Filtragem de repiques de contato (*Debouncing* de 50 ms) para eliminar ruídos ópticos e mecânicos.
   * Validação de qualidade de leitura (`StatusCode == GOOD`).
   * Rastreabilidade e *Data Lineage* com carimbos de data/hora UTC (ISO 8601).

2. **Detecção de Anomalias por Rede de Petri ($p_1 \dots p_{16}$):**
   * 🔴 **Sensor de Altura Stuck OFF:** Detecta caixas que atingiram a mesa sem leitura prévia de altura.
   * 🔴 **Sensor de Presença Stuck ON:** Detecta sensor travado em nível alto por mais de 2.5s para evitar engavetamento.
   * 🔴 **Timeout de Transporte:** Identifica caixas presas ou motor travado se a esteira rodar mais de 4.0s sem avanço de peça.

3. **Ação Autônoma e Parada de Emergência:**
   * Ao detectar qualquer anomalia crítica, o Gêmeo Digital aciona a **Parada de Emergência (`PLC_PRG.desligar = True`)** imediatamente via OPC UA, interrompendo a linha física antes de ocorrer quebra de equipamento.
   * O operador pode interagir no Dashboard, verificar a anomalia na tabela de auditoria e clicar em **`RESET`** para liberar a linha.

4. **Padronização Indústria 4.0 (Asset Administration Shell - Eclipse BaSyx):**
   * Submodelo `TechnicalIdentification` com metadados do ativo e normas aplicadas.
   * Submodelo `OperationalData` com telemetria em tempo real.
   * Submodelo `HealthAndDiagnostics` com score de saúde e histórico de anomalias.
   * Botão no Dashboard para **download do arquivo oficial AAS no formato JSON**.
