"""Motor de análise da carteira: cotações, renda fixa, IA e Telegram.

Este pacote é o coração da análise e roda sempre pelo script isolado
`scripts/analisar.py` — pelo agendador de tarefas, pelo terminal ou disparado
pela interface web. A aplicação Node cuida do cadastro da carteira e da
apresentação; ela nunca importa este pacote, apenas executa o script.
"""
