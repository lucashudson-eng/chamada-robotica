from google.colab import drive
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import date, datetime, timedelta
import os

# ⚙️ CONFIGURAÇÃO
CAMINHO_DRIVE = 'Robo_Classroom'  # Nome da pasta no seu Drive com credentials.json e token.json

def montar_drive():
    drive.mount('/content/gdrive', force_remount=True)
    return f'/content/gdrive/My Drive/{CAMINHO_DRIVE}'

def criar_servico(credentials_path, token_path):
    SCOPES = [
      'https://www.googleapis.com/auth/classroom.courses',
      'https://www.googleapis.com/auth/classroom.coursework.students',
      'https://www.googleapis.com/auth/classroom.topics.readonly',
      'https://www.googleapis.com/auth/classroom.rosters'
    ]
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('classroom', 'v1', credentials=creds)

def criar_chamada_agora(service, course_id, topic_id):
    from datetime import datetime, timedelta

    agora = datetime.now()
    dia_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-Feira', 'Sexta-feira', 'Sábado', 'Domingo'][agora.weekday()]

    titulo = f'Frequência {agora.day}/{agora.month}/{agora.year} ({dia_semana})'

    # Entrega 2 horas após o momento atual
    data_entrega = agora + timedelta(hours=2)

    tarefa = {
        'title': titulo,
        'state': 'PUBLISHED',  # publica imediatamente
        'dueDate': {
            'year': data_entrega.year,
            'month': data_entrega.month,
            'day': data_entrega.day
        },
        'dueTime': {
            'hours': data_entrega.hour,
            'minutes': data_entrega.minute
        },
        'maxPoints': 1,
        'workType': 'MULTIPLE_CHOICE_QUESTION',
        'submissionModificationMode': 'MODIFIABLE_UNTIL_TURNED_IN',
        'multipleChoiceQuestion': {'choices': ['Presente']},
        'assigneeMode': 'ALL_STUDENTS',
        'topicId': topic_id
    }

    atividade = service.courses().courseWork().create(courseId=course_id, body=tarefa).execute()
    print(f"✅ Tarefa criada com sucesso: {atividade['title']}")

# EXECUÇÃO

caminho = montar_drive()
service = criar_servico(f"{caminho}/credentials.json", f"{caminho}/token.json")

# Escolher curso automaticamente pelo nome
nome_curso_desejado = "Turma Teste"
courses = service.courses().list(pageSize=40, courseStates='ACTIVE').execute().get('courses', [])

course_id = None
for c in courses:
    if c['name'] == nome_curso_desejado:
        course_id = c['id']
        print(f"✅ Curso selecionado: {c['name']}")
        break

if not course_id:
    raise Exception(f"❌ Curso '{nome_curso_desejado}' não encontrado.")

# Escolher tópico automaticamente pelo nome
nome_topico_desejado = "Frequência"
topics = service.courses().topics().list(courseId=course_id).execute().get('topic', [])

topic_id = None
for t in topics:
    if t['name'] == nome_topico_desejado:
        topic_id = t['topicId']
        print(f"✅ Tópico selecionado: {t['name']}")
        break

if not topic_id:
    raise Exception(f"❌ Tópico '{nome_topico_desejado}' não encontrado.")

# Criar chamada
criar_chamada_agora(service, course_id, topic_id)

def responder_chamada_manual(service, course_id):
    # Seleciona a chamada
    courseworks = service.courses().courseWork().list(courseId=course_id).execute()
    print("\nAtividades disponíveis:")
    chamadas = [cw for cw in courseworks.get('courseWork', []) if cw['title'].startswith('Frequência ')]
    for i, cw in enumerate(chamadas):
        print(f"{i}: {cw['title']}")

    chamada_index = int(input("Digite o índice da chamada a ser respondida: "))
    coursework_id = chamadas[chamada_index]['id']

    # Lista todos os alunos da turma
    students = service.courses().students().list(courseId=course_id).execute()
    alunos = {
        student['profile']['name']['fullName'].lower(): student['userId']
        for student in students['students']
    }

    # Lista todas as submissões da atividade
    submissions = service.courses().courseWork().studentSubmissions().list(
        courseId=course_id,
        courseWorkId=coursework_id
    ).execute()['studentSubmissions']

    submissions_dict = {sub['userId']: sub['id'] for sub in submissions}

    print("\n📢 Digite o nome do aluno exatamente como está no Classroom.")
    print("Digite 'fim' para encerrar.\n")

    while True:
        nome = input("Nome do aluno: ").strip().lower()
        if nome == "fim":
            break
        if nome in alunos:
            user_id = alunos[nome]
            submission_id = submissions_dict[user_id]

            body = {
                'draftGrade': 1,
                'assignedGrade': 1
            }

            service.courses().courseWork().studentSubmissions().patch(
                courseId=course_id,
                courseWorkId=coursework_id,
                id=submission_id,
                updateMask='draftGrade,assignedGrade',
                body=body
            ).execute()

            print(f"✅ Presença registrada para: {nome.title()}")
        else:
            print(f"❌ Aluno não encontrado: {nome}")

responder_chamada_manual(service, course_id)