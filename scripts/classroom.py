from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta, timezone
import os

# ⚙️ CONFIGURAÇÃO
CONFIG_PATH = 'config'  # Pasta local com credentials.json e token.json

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
    # Usa UTC para evitar problemas de fuso
    agora_utc = datetime.now(timezone.utc)
    data_entrega_utc = agora_utc + timedelta(hours=2)

    dia_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-Feira', 'Sexta-feira', 'Sábado', 'Domingo'][agora_utc.weekday()]

    titulo = f'Frequência {agora_utc.day}/{agora_utc.month}/{agora_utc.year} ({dia_semana})'

    tarefa = {
        'title': titulo,
        'state': 'PUBLISHED',  # publica imediatamente
        'dueDate': {
            'year': data_entrega_utc.year,
            'month': data_entrega_utc.month,
            'day': data_entrega_utc.day
        },
        'dueTime': {
            'hours': data_entrega_utc.hour,
            'minutes': data_entrega_utc.minute,
            'seconds': data_entrega_utc.second
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
    return atividade['id']

def responder_chamada_manual(service, course_id, coursework_id):
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
    ).execute().get('studentSubmissions', [])

    submissions_dict = {sub['userId']: sub['id'] for sub in submissions}

    print("\n📢 Digite o nome do aluno exatamente como está no Classroom.")
    print("Digite 'fim' para encerrar.\n")

    while True:
        nome = input("Nome do aluno: ").strip().lower()
        if nome == "fim":
            break
        if nome in alunos:
            user_id = alunos[nome]
            submission_id = submissions_dict.get(user_id)
            if not submission_id:
                print(f"❌ Nenhuma submissão encontrada para o aluno: {nome.title()}")
                continue

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

# EXECUÇÃO

credentials_path = os.path.join(CONFIG_PATH, 'credentials.json')
token_path = os.path.join(CONFIG_PATH, 'token.json')

service = criar_servico(credentials_path, token_path)

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
coursework_id = criar_chamada_agora(service, course_id, topic_id)

# Responder chamada manualmente
responder_chamada_manual(service, course_id, coursework_id)
