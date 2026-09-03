class RedePetri:
    def __init__(self, estados=None, lugares2transicoes=None,
                 transicoes2lugares=None, eventos=None):

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

    # ---------------------------------------------------------
    # ESTADOS
    # ---------------------------------------------------------

    def adicionar_estado(self, lugar, fichas=0):
        self.estados[lugar] = fichas

    # ---------------------------------------------------------
    # TRANSIÇÕES
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # EVENTOS
    # ---------------------------------------------------------

    def adicionar_evento(self, evento, transicoes):
        self.eventos[evento] = transicoes

    # ---------------------------------------------------------
    # TRANSIÇÕES DISPONÍVEIS
    # ---------------------------------------------------------

    def transicoes_disponiveis(self):
        """
        Retorna as transições habilitadas pelos estados atuais.

        Uma transição está disponível quando existe pelo menos
        um lugar de origem com ficha.
        """

        disponiveis = {}

        for lugar, fichas in self.estados.items():

            # Se não há ficha, nenhuma transição pode sair daqui
            if fichas <= 0:
                continue

            # Verifica se existem transições saindo desse lugar
            if lugar not in self.lugares2transicoes:
                continue

            for transicao in self.lugares2transicoes[lugar]:

                if transicao not in disponiveis:
                    disponiveis[transicao] = []

                disponiveis[transicao].append(lugar)

        return disponiveis

    # ---------------------------------------------------------
    # PROCESSAMENTO DE EVENTO
    # ---------------------------------------------------------

    def processar_evento(self, evento):

        # 1. Verificar o evento
        if evento not in self.eventos:
            return False, (
                f"Falha: evento '{evento}' não está cadastrado."
            )

        transicoes_evento = self.eventos[evento]

        # 2. Encontrar transições habilitadas
        disponiveis = self.transicoes_disponiveis()

        # 3. Encontrar uma transição associada ao evento que esteja habilitada
        transicao_escolhida = None
        lugar_origem = None

        for transicao in transicoes_evento:

            if transicao in disponiveis:

                transicao_escolhida = transicao
                lugar_origem = disponiveis[transicao][0]

                break

        # 4. Se nenhuma transição estiver habilitada
        if transicao_escolhida is None:
            return False, (
                f"Falha: nenhuma transição associada ao evento "
                f"'{evento}' está habilitada."
            )

        # 5. Consumir ficha do lugar de origem
        self.estados[lugar_origem] -= 1

        # 6. Obter lugares de destino
        lugares_destino = self.transicoes2lugares[transicao_escolhida]

        # 7. Adicionar fichas aos lugares de destino
        for lugar in lugares_destino:
            if lugar in self.estados:
                self.estados[lugar] += 1

        return True, (
            f"Evento '{evento}' processado. "
            f"Transição '{transicao_escolhida}' disparada "
            f"a partir de '{lugar_origem}'."
        )

    # ---------------------------------------------------------
    # VISUALIZAÇÃO
    # ---------------------------------------------------------

    def mostrar_estados(self):

        print("Estados atuais:")

        for lugar, fichas in self.estados.items():
            print(f"  {lugar}: {fichas}")