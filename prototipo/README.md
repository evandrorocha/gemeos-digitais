# 🏭 Protótipo de Gêmeo Digital Industrial (Digital Twin)

Este projeto implementa o **Gêmeo Digital (Digital Twin)** da linha de triagem de caixas por altura (*Sorting by Height*), baseado na arquitetura de 3 camadas da norma **ISO 23247** e nos princípios de governança de dados da norma **ISO/IEC 30173:2025**.

---

## 🏛️ Arquitetura do Projeto

```text
prototipo/
│
├── factoryio/                      # 📁 1. Camada do Ativo Físico e Automação
│   ├── SortingByHeight_Basic.project  # Lógica Ladder desenvolvida no CODESYS
│   ├── SortingByHeight_Basic.xml      # Mapa de símbolos OPC UA
│   ├── index.html                     # Documentação das tags da cena
│   └── docs/                          # Apresentações e especificações do projeto
│
├── gemeo-digital/                  # 📁 2. Camada do Núcleo do Gêmeo Digital (Python)
│   ├── config.py                      # Parâmetros de temporização e nós OPC UA
│   ├── data_sanitizer.py              # Sanitização (Debouncing 50ms, qualidade e linhagem)
│   ├── petri_engine.py                # Motor da Rede de Petri & Detecção de Anomalias (Stuck ON/OFF, Timeout)
│   ├── aas_model.py                   # Modelo de Casca Administrativa (Asset Administration Shell - BaSyx)
│   └── opc_connector.py               # Conector OPC UA assíncrono bidirecional (asyncua)
│
├── dashboard/                      # 📁 3. Camada de Aplicação do Usuário / Supervisório
│   └── app.py                         # Interface Web em Streamlit com painel ao vivo e injeção de falhas
│
├── Dockerfile                      # Empacotamento Docker da aplicação
├── docker-compose.yml              # Orquestração para execução em qualquer máquina com 1 comando
└── requirements.txt                # Dependências Python
```

---

## 🚀 Como Executar

### Opção A: Executando com Docker (Recomendado)

1. Certifique-se de que o **CODESYS** e o **Factory I/O** estão rodando e com o CLP em `[EXECUÇÃO]`.
2. No terminal, dentro da pasta `prototipo/`, execute:
   ```bash
   docker compose up --build
   ```
3. Abra o navegador em: **`http://localhost:8501`**

---

### Opção B: Executando Diretamente no Python Local

1. Instale as dependências:
   ```bash
   pip install -r prototipo/requirements.txt
   ```
2. Inicie o Dashboard do Gêmeo Digital:
   ```bash
   streamlit run prototipo/dashboard/app.py
   ```
3. O painel abrirá automaticamente no seu navegador.

---

## 🔍 Funcionalidades Implementadas

1. **Sanitização de Dados Industriais (ISO/IEC 30173):**
   * Filtragem de repiques de contato (*Debouncing* de 50 ms) para eliminar ruído óptico/mecânico.
   * Validação de qualidade de leitura (`StatusCode == GOOD`).
   * Rastreabilidade e *Data Lineage* com carimbos de data/hora ISO 8601.

2. **Detecção de Anomalias por Rede de Petri:**
   * **Falha 1 (Sensor de Altura Stuck OFF):** Identifica caixas altas que chegaram na mesa de desvio sem o sinal do sensor óptico de topo.
   * **Falha 2 (Sensor de Presença Stuck ON):** Detecta sensor travado em 1 permanente para prevenir colisões/engavetamento.
   * **Falha 3 (Timeout de Transporte):** Identifica esteira patinando ou caixas travadas no meio do percurso (> 4.0s).

3. **Controle Supervisório e Ação Autônoma:**
   * Ao detectar qualquer anomalia crítica, o Gêmeo Digital aciona a **Parada de Emergência (`STOP`)** no CODESYS via OPC UA.
   * O operador pode interagir no Dashboard, reconhecer a anomalia e enviar o comando de **`RESET` e `START`** para retomar a produção.

4. **Padrão da Indústria 4.0 (Asset Administration Shell - Eclipse BaSyx):**
   * Submodelo `TechnicalIdentification` com metadados do ativo.
   * Submodelo `OperationalData` com as variáveis em tempo real.
   * Submodelo `HealthAndDiagnostics` com score de saúde e histórico de anomalias.
   * Exportação do arquivo oficial AAS no formato JSON.
