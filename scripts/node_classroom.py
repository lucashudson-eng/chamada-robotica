#!/usr/bin/env python3
import rospy
from std_msgs.msg import String
import rospkg
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
import os

rospack = rospkg.RosPack()
package_path = rospack.get_path('chamada_robotica')
CONFIG_PATH = os.path.join(package_path, 'config')

service = None
course_id = None
topic_id = None
coursework_id = None
alunos = {}
submissions = {}

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

def get_course_id(nome_curso):
    cursos = service.courses().list(pageSize=40, courseStates='ACTIVE').execute().get('courses', [])
    for c in cursos:
        if c['name'] == nome_curso:
            rospy.loginfo(f"Curso encontrado: {c['name']}")
            return c['id']
    return None

def get_topic_id(course_id, nome_topico):
    topicos = service.courses().topics().list(courseId=course_id).execute().get('topic', [])
    for t in topicos:
        if t['name'] == nome_topico:
            rospy.loginfo(f"Tópico encontrado: {t['name']}")
            return t['topicId']
    return None

def criar_chamada_agora(course_id, topic_id):
    agora_utc = datetime.now(timezone.utc)
    entrega_utc = agora_utc + timedelta(hours=2)
    dia_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-Feira', 'Sexta-feira', 'Sábado', 'Domingo'][agora_utc.weekday()]
    titulo = f'Frequência {agora_utc.day}/{agora_utc.month}/{agora_utc.year} ({dia_semana})'

    tarefa = {
        'title': titulo,
        'state': 'PUBLISHED',
        'dueDate': {
            'year': entrega_utc.year,
            'month': entrega_utc.month,
            'day': entrega_utc.day
        },
        'dueTime': {
            'hours': entrega_utc.hour,
            'minutes': entrega_utc.minute,
            'seconds': entrega_utc.second
        },
        'maxPoints': 1,
        'workType': 'MULTIPLE_CHOICE_QUESTION',
        'submissionModificationMode': 'MODIFIABLE_UNTIL_TURNED_IN',
        'multipleChoiceQuestion': {'choices': ['Presente']},
        'assigneeMode': 'ALL_STUDENTS',
        'topicId': topic_id
    }

    atividade = service.courses().courseWork().create(courseId=course_id, body=tarefa).execute()
    rospy.loginfo(f"Tarefa criada: {atividade['title']}")
    return atividade['id']

def carregar_alunos(course_id):
    resp = service.courses().students().list(courseId=course_id).execute()
    dic = {}
    for student in resp.get('students', []):
        nome = student['profile']['name']['fullName'].lower()
        dic[nome] = student['userId']
    rospy.loginfo(f"{len(dic)} alunos carregados.")
    return dic

def carregar_submissions(course_id, coursework_id):
    resp = service.courses().courseWork().studentSubmissions().list(courseId=course_id, courseWorkId=coursework_id).execute()
    subs = resp.get('studentSubmissions', [])
    dic = {sub['userId']: sub['id'] for sub in subs}
    rospy.loginfo(f"{len(dic)} submissões carregadas.")
    return dic

def callback(msg):
    nome = msg.data.strip().lower()
    rospy.loginfo(f"Recebido nome do aluno: {nome}")

    if nome not in alunos:
        rospy.logwarn(f"Aluno não encontrado: {nome}")
        return

    user_id = alunos[nome]
    submission_id = submissions.get(user_id)
    if not submission_id:
        rospy.logwarn(f"Nenhuma submissão encontrada para o aluno: {nome}")
        return

    body = {
        'draftGrade': 1,
        'assignedGrade': 1
    }
    try:
        service.courses().courseWork().studentSubmissions().patch(
            courseId=course_id,
            courseWorkId=coursework_id,
            id=submission_id,
            updateMask='draftGrade,assignedGrade',
            body=body
        ).execute()
        rospy.loginfo(f"Presença registrada para: {nome.title()}")
    except Exception as e:
        rospy.logerr(f"Erro ao registrar presença para {nome}: {e}")

if __name__ == '__main__':
    try:
        rospy.init_node('node_classroom')

        nome_curso = rospy.get_param('~nome_curso')
        nome_topico = rospy.get_param('~nome_topico')

        credentials_path = os.path.join(CONFIG_PATH, 'credentials.json')
        token_path = os.path.join(CONFIG_PATH, 'token.json')

        service = criar_servico(credentials_path, token_path)
        
        course_id = get_course_id(nome_curso)
        if not course_id:
            rospy.logfatal(f"Curso '{nome_curso}' não encontrado.")
            exit(1)

        topic_id = get_topic_id(course_id, nome_topico)
        if not topic_id:
            rospy.logfatal(f"Tópico '{nome_topico}' não encontrado.")
            exit(1)

        coursework_id = criar_chamada_agora(course_id, topic_id)
        alunos = carregar_alunos(course_id)
        submissions = carregar_submissions(course_id, coursework_id)

        rospy.Subscriber('/aluno_detectado', String, callback)

        rospy.loginfo("Nó iniciado, aguardando nomes de alunos no tópico /aluno_detectado...")
        rospy.spin()
    except Exception as e:
        rospy.logfatal(f"Erro inesperado: {e}")