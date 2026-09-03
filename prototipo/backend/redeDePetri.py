class RedePetri:
    def __init__(self, 
                 estados=None, 
                 lugares2transicoes=None,
                 transicoes2lugares=None, 
                 eventos=None, 
                 variaveis=None,
                 condicoes=None):

        # Módulo dos estados
        # {lugar: quantidade_de_fichas}
        self.estados = estados if estados is not None else {}

        # Módulo que indica quais transições saem de cada lugar
        # {lugar: [transicoes]}
        self.lugares2transicoes = (
            lugares2transicoes
            if lugares2transicoes is not None
            else {}
        )

        # Módulo que indica quais lugares são alcançados por cada transição
        # {transicao: [lugares]}
        self.transicoes2lugares = (
            transicoes2lugares
            if transicoes2lugares is not None
            else {}
        )

        # Módulo dos eventos
        # {evento: [transicoes]}
        self.eventos = eventos if eventos is not None else {}

        # Conjunto de variáveis internas do sistema
        # {"variavel": valor}
        self.variaveis = variaveis if variaveis is not None else {}

        # Conjunto que indica associacao entre transicao e variavel interna
        # {"transicao": ("variavel", valor)}
        self.condicoes = condicoes if condicoes is not None else {}

    def adicionar_estado(self, lugar, fichas=0):
        self.estados[lugar] = fichas

    def adicionar_transicao(self, lugar_origem, transicao, lugares_destino):
        """
        Adiciona uma transição à rede.
        """

        # Adiciona a transição ao lugar de origem
        if lugar_origem not in self.lugares2transicoes:
            self.lugares2transicoes[lugar_origem] = []

        if transicao not in self.lugares2transicoes[lugar_origem]:
            self.lugares2transicoes[lugar_origem].append(transicao)

        # Adiciona os lugares de destino à transição
        self.transicoes2lugares[transicao] = lugares_destino

    def adicionar_evento(self, evento, transicoes):
        self.eventos[evento] = transicoes

    def adicionar_variavel(self, nome, valor=0):
        self.variaveis[nome] = valor
    
    def atualizar_variavel(self, nome, valor):
        if nome not in self.variaveis:
            raise ValueError(
                f"Variável '{nome}' não está cadastrada."
            )
        self.variaveis[nome] = valor
    
    def transicao_pode_disparar(self, transicao):
        # Verificar condição interna
        if transicao in self.condicoes:

            variavel, valor_esperado = self.condicoes[transicao]

            if self.variaveis.get(variavel) != valor_esperado:
                return False

        return True
    
    def transicoes_disponiveis(self):
        """
        Retorna as transições habilitadas pelos estados atuais.

        Uma transição está disponível quando existe pelo menos
        um lugar de origem com ficha.
        """

        # Primeiro, descobrir todos os lugares de entrada de cada transição
        entradas = {}

        for lugar, transicoes in self.lugares2transicoes.items():
            for transicao in transicoes:
                if transicao not in entradas:
                    entradas[transicao] = []
                entradas[transicao].append(lugar)

        disponiveis = {}

        # Verificar se TODOS os lugares de entrada possuem pelo menos uma ficha
        for transicao, lugares in entradas.items():

            # 1. Verificar fichas
            fichas_disponiveis = all(self.estados.get(lugar, 0) > 0 for lugar in lugares)
            if not fichas_disponiveis:
                continue

            # 2. Verificar variável interna
            if not self.transicao_pode_disparar(transicao):
                continue

            disponiveis[transicao] = lugares

        return disponiveis
    
    def processar_evento(self, evento):

        mensagens = []

        # 1. Verificar o evento
        if evento not in self.eventos:
            return False, (
                f"Falha: evento '{evento}' nao esta cadastrado."
            )

        transicoes_evento = self.eventos[evento]

        # 2. Encontrar transições habilitadas
        disponiveis = self.transicoes_disponiveis()

        # 3. Encontrar uma transição associada ao evento que esteja habilitada
        transicoes_escolhidas = []
        lugar_origem = None

        for transicao in transicoes_evento:
            if transicao in disponiveis:
                transicoes_escolhidas.append(transicao)

        # 4. Se nenhuma transição estiver habilitada
        if not transicoes_escolhidas:
            return False, (
                f"Falha: nenhuma transicao associada ao evento "
                f"'{evento}' esta habilitada."
            )

        # 5. Disparar as transições associadas
        for transicao in transicoes_escolhidas:
            lugares_origem = disponiveis[transicao]

            for lugar in lugares_origem:
                self.estados[lugar_origem] -= 1

            lugares_destino = self.transicoes2lugares[transicao]
            for lugar in lugares_destino:
                if lugar in self.estados:
                    self.estados[lugar] += 1

            mensagens.append(
                f"Evento '{evento}': "
                f"transicao '{transicao}' disparada "
                f"a partir de '{lugar_origem}'."
            )

        # 6. Disparar automaticamente as transições lambda
        while True:
            # Atualiza as transições habilitadas
            disponiveis = self.transicoes_disponiveis()

            transicao_lambda = None
            lugar_origem = None

            # Procurar uma transição lambda habilitada
            for transicao, lugares in disponiveis.items():

                # Uma transição é lambda se não estiver associada a nenhum evento
                if not any(transicao in transicoes for transicoes in self.eventos.values()):
                    transicao_lambda = transicao
                    lugar_origem = lugares[0]
                    break

            # Nenhuma lambda habilitada
            if transicao_lambda is None:
                break

            # Disparar lambda
            self.estados[lugar_origem] -= 1

            lugares_destino = self.transicoes2lugares[transicao_lambda]

            for lugar in lugares_destino:

                if lugar in self.estados:
                    self.estados[lugar] += 1

            mensagens.append(
                f"Transicao lambda '{transicao_lambda}' "
                f"disparada a partir de '{lugar_origem}'."
            )

        return True, "\n".join(mensagens)

    # VISUALIZAÇÃO
    def mostrar_estados(self):

        print("Estados atuais:")

        for lugar, fichas in self.estados.items():
            print(f"  {lugar}: {fichas}")