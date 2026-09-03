class RedePetri:
    def __init__(self, lugares=None, transicoes=None, eventos=None):
        """
        lugares:
            Dicionário contendo os lugares e suas fichas.
            Exemplo:
                {"p1": 2, "p2": 0}

        transicoes:
            Dicionário que mapeia:
                lugar -> {transição: [lugares_destino]}

            Exemplo:
                {"p1": {"t1": ["p1", "p2"], "t2": ["p3"]}, "p2": {"t3": ["p4"]}}

        eventos:
            Dicionário que mapeia:
                evento/sensor -> [transições]

            Exemplo:
                {"sensor1": ["t1", "t2"], "sensor2": ["t3"]}
        """

        self.lugares = lugares if lugares is not None else {}
        self.transicoes = transicoes if transicoes is not None else {}
        self.eventos = eventos if eventos is not None else {}

    def adicionar_estado(self, lugar, fichas=0):
        """Adiciona um lugar à rede."""
        self.lugares[lugar] = fichas

    def adicionar_transicao(self, lugar, transicao, destinos):
        """
        Adiciona uma transição associada a um lugar.

        Exemplo:
            adicionar_transicao("p1", "t1", ["p1", "p2"])
        """

        if lugar not in self.transicoes:
            self.transicoes[lugar] = {}

        self.transicoes[lugar][transicao] = destinos

    def adicionar_evento(self, evento, transicoes):
        """Associa um evento a uma ou mais transições."""
        self.eventos[evento] = transicoes

    def _transicoes_disponiveis(self):
        """
        Retorna as transições disponíveis nos lugares
        que possuem pelo menos uma ficha.

        Retorno:
            {
                "t1": ["p1"],
                "t2": ["p3"]
            }
        """

        disponiveis = {}

        for lugar, fichas in self.lugares.items():

            # O lugar precisa possuir pelo menos uma ficha
            if fichas <= 0:
                continue

            # Verifica as transições existentes nesse lugar
            if lugar not in self.transicoes:
                continue

            for transicao in self.transicoes[lugar]:

                if transicao not in disponiveis:
                    disponiveis[transicao] = []

                disponiveis[transicao].append(lugar)

        return disponiveis

    def processar_evento(self, evento):
        """
        Processa um novo evento recebido pela rede.

        Etapas:
        1. Procura as transições associadas ao evento.
        2. Verifica quais dessas transições estão habilitadas.
        3. Dispara a transição.
        4. Atualiza as fichas.

        Retorna:
            (True, mensagem)  -> sucesso
            (False, mensagem) -> falha
        """

        # --------------------------------------------------
        # 1. Verificar se o evento existe
        # --------------------------------------------------

        if evento not in self.eventos:
            return False, f"Evento '{evento}' não está cadastrado."

        transicoes_evento = self.eventos[evento]

        # --------------------------------------------------
        # 2. Verificar quais transições estão disponíveis
        # --------------------------------------------------

        transicoes_disponiveis = self._transicoes_disponiveis()

        # --------------------------------------------------
        # 3. Procurar uma transição do evento que esteja
        #    habilitada
        # --------------------------------------------------

        transicao_escolhida = None
        lugar_origem = None

        for transicao in transicoes_evento:

            if transicao in transicoes_disponiveis:

                transicao_escolhida = transicao

                # Lugar que habilitou a transição
                lugar_origem = transicoes_disponiveis[transicao][0]

                break

        # --------------------------------------------------
        # 4. Nenhuma transição disponível
        # --------------------------------------------------

        if transicao_escolhida is None:
            return (
                False,
                f"Falha: nenhuma transição associada ao evento "
                f"'{evento}' está habilitada."
            )

        # --------------------------------------------------
        # 5. Obter os lugares de destino
        # --------------------------------------------------

        destinos = self.transicoes[lugar_origem][transicao_escolhida]

        # --------------------------------------------------
        # 6. Consumir uma ficha do lugar de origem
        # --------------------------------------------------

        self.lugares[lugar_origem] -= 1

        # --------------------------------------------------
        # 7. Produzir fichas nos lugares de destino
        # --------------------------------------------------

        for destino in destinos:

            # Caso o lugar ainda não exista
            if destino not in self.lugares:
                self.lugares[destino] = 0

            self.lugares[destino] += 1

        return (
            True,
            f"Evento '{evento}' processado. "
            f"Transição '{transicao_escolhida}' disparada "
            f"a partir de '{lugar_origem}'."
        )

    def mostrar_estados(self):
        """Exibe o estado atual da rede."""
        print("Estados atuais:")

        for lugar, fichas in self.lugares.items():
            print(f"  {lugar}: {fichas} ficha(s)")