from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, make_response, abort
import mysql.connector
from mysql.connector import Error
import json
import os
import re
import base64
import io
from PIL import Image
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

# ==============================================================================
# CONFIGURAÇÕES INICIAIS DO APP
# ==============================================================================
app = Flask(__name__, template_folder='view', static_folder='static')
app.secret_key = 'segredo_super_importante'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 1800

CONFIGURACOES_PADRAO = {
    'notificacoes_email': True,
    'notificacoes_push': True,
    'alertas_prazos': True,
    'notificacoes_aulas': True,
    'notificacoes_notas': True,
    'email_diario': False,
    'email_semanal': True,
    'privacidade_perfil': 'alunos',
    'tempo_sessao': 30,
    'backup_automatico': False,
    'registro_atividades': True,
    'tema_sistema': 'claro',
    'idioma': 'pt-BR',
    'tamanho_fonte': 1.0,
    'alto_contraste': False
}

# ==============================================================================
# CONEXÃO COM BANCO DE DADOS
# ==============================================================================
def conectar():
    try:
        conexao = mysql.connector.connect(
            host="tini.click",
            user="comunidade_escolar",
            password="f588be551b488db55a41b825214a8c83",
            database="comunidade_escolar",
            port=3306
        )
        if conexao.is_connected():
            return conexao
        else:
            return None
    except Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

# ==============================================================================
# DECORATORS E MIDDLEWARE
# ==============================================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'logado' not in session or not session.get('logado'):
            flash('Por favor, faça login para acessar esta página.', 'erro')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.before_request
def carregar_configuracoes_usuario():
    if session.get('logado'):
        usuario_id = None
        tipo_usuario = session.get('tipo')
        
        if tipo_usuario == 'aluno':
            usuario_id = session.get('id_aluno')
        elif tipo_usuario == 'professor':
            usuario_id = session.get('id_professor')
        
        if usuario_id:
            if 'configuracoes' not in session:
                config = carregar_configuracoes_banco(usuario_id, tipo_usuario)
                session['configuracoes'] = config
            
            if 'configuracoes' in session:
                config = session['configuracoes']
                if 'tempo_sessao' in config:
                    try:
                        tempo_sessao = int(config['tempo_sessao'])
                        app.config['PERMANENT_SESSION_LIFETIME'] = tempo_sessao * 60
                        session.permanent = True
                    except (ValueError, TypeError):
                        pass

@app.context_processor
def injectar_configuracoes():
    if session.get('logado'):
        configuracoes = session.get('configuracoes', CONFIGURACOES_PADRAO.copy())
        for key, value in CONFIGURACOES_PADRAO.items():
            if key not in configuracoes:
                configuracoes[key] = value
        return dict(configuracoes=configuracoes)
    return dict(configuracoes=CONFIGURACOES_PADRAO)

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def carregar_configuracoes_banco(usuario_id, tipo_usuario):
    conexao = conectar()
    config_retornada = CONFIGURACOES_PADRAO.copy()
    if conexao:
        try:
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT config_json FROM configuracoes WHERE usuario_id = %s AND tipo_usuario = %s", (usuario_id, tipo_usuario))
            resultado = cursor.fetchone()
            if resultado and resultado['config_json']:
                try:
                    if isinstance(resultado['config_json'], str):
                        dados_banco = json.loads(resultado['config_json'])
                    else:
                        dados_banco = resultado['config_json']
                    
                    for key, value in CONFIGURACOES_PADRAO.items():
                        if key in dados_banco:
                            config_retornada[key] = dados_banco[key]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Erro config: {e}")
        finally:
            if conexao.is_connected():
                cursor.close()
                conexao.close()
    return config_retornada

def salvar_configuracoes_banco(usuario_id, tipo_usuario, config_data):
    conexao = conectar()
    sucesso = False
    if conexao:
        try:
            cursor = conexao.cursor()
            cursor.execute("SELECT id FROM configuracoes WHERE usuario_id = %s AND tipo_usuario = %s", (usuario_id, tipo_usuario))
            existe = cursor.fetchone()
            config_json = json.dumps(config_data)
            
            if existe:
                cursor.execute("UPDATE configuracoes SET config_json = %s, atualizado_em = NOW() WHERE usuario_id = %s AND tipo_usuario = %s", (config_json, usuario_id, tipo_usuario))
            else:
                cursor.execute("INSERT INTO configuracoes (usuario_id, tipo_usuario, config_json, criado_em, atualizado_em) VALUES (%s, %s, %s, NOW(), NOW())", (usuario_id, tipo_usuario, config_json))
            conexao.commit()
            sucesso = True
        except Exception as e:
            print(f"Erro salvar config: {e}")
            conexao.rollback()
        finally:
            if conexao.is_connected():
                cursor.close()
                conexao.close()
    return sucesso

def registrar_atividade(usuario_id, tipo_usuario, tipo, descricao):
    conexao = conectar()
    if conexao:
        try:
            cursor = conexao.cursor()
            cursor.execute("INSERT INTO atividades_usuario (usuario_id, tipo_usuario, tipo_atividade, descricao, criado_em) VALUES (%s, %s, %s, %s, NOW())", (usuario_id, tipo_usuario, tipo, descricao))
            conexao.commit()
        except: pass
        finally:
            if conexao.is_connected():
                cursor.close()
                conexao.close()

def validar_email(email: str) -> bool:
    print(f"DEBUG validar_email: Validando '{email}'")
    padrao = r'^[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email) is not None

def validar_senha(senha: str) -> bool:
    return senha is not None and len(senha) >= 4




# Configurações
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_profile_photo(photo_data, filename=None, file_data=None):
    """Processa a foto de perfil enviada"""
    try:
        # Se veio como base64 (do campo hidden)
        if photo_data and photo_data.startswith('data:image'):
            # Extrair a parte base64
            header, encoded = photo_data.split(',', 1)
            
            # Decodificar base64
            image_data = base64.b64decode(encoded)
            
            # Abrir imagem com PIL
            img = Image.open(io.BytesIO(image_data))
            
        # Se veio como arquivo (do input file)
        elif file_data:
            # Verificar tamanho
            file_data.seek(0, os.SEEK_END)
            size = file_data.tell()
            file_data.seek(0)
            
            if size > MAX_FILE_SIZE:
                return None, "Arquivo muito grande (máx. 5MB)"
            
            img = Image.open(file_data)
        else:
            return None, None
        
        # Converter para RGB se necessário
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Redimensionar mantendo proporção
        img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        # Criar imagem circular (opcional)
        # Se quiser imagens circulares, descomente abaixo:
        # mask = Image.new('L', img.size, 0)
        # draw = ImageDraw.Draw(mask)
        # draw.ellipse((0, 0) + img.size, fill=255)
        # result = Image.new('RGB', img.size)
        # result.paste(img, mask=mask)
        # img = result
        
        # Salvar em buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        
        # Converter para base64 para armazenar no banco
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Retornar como string base64
        return f"data:image/jpeg;base64,{img_base64}", None
        
    except Exception as e:
        print(f"Erro ao processar imagem: {str(e)}")
        return None, "Erro ao processar imagem"

# ==============================================================================
# ROTAS PÚBLICAS E DE AUTENTICAÇÃO
# ==============================================================================
@app.route('/')
def boas_vindas():
    return render_template('usuario/inicio.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Se já estiver logado, redireciona
    if session.get('logado'):
        if session.get('tipo') == 'aluno':
            return redirect(url_for('home_aluno'))
        else:
            return redirect(url_for('home_professor'))
    
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '').strip()
        
        print(f"DEBUG LOGIN: Tentando login - Usuário: '{usuario}'")
        
        if not usuario or not senha:
            flash('Preencha todos os campos!', 'erro')
            return render_template('usuario/login.html')
        
        conexao = conectar()
        if not conexao:
            flash('Erro de conexão com o banco.', 'erro')
            return render_template('usuario/login.html')

        try:
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT * FROM usuarios WHERE apelido = %s", (usuario,))
            user = cursor.fetchone()
            
            if user:
                print(f"DEBUG LOGIN: Usuário encontrado.")
                
                if user['senha'] == senha:
                    print(f"DEBUG LOGIN: Senha correta! Login bem-sucedido.")
                    
                    session['logado'] = True
                    session['tipo'] = user['tipo']
                    session['usuario'] = user['apelido']
                    session['id'] = user['id']
                    
                    if user['tipo'] == 'professor':
                        session['id_professor'] = user['id']
                        destino = 'home_professor'
                    else:
                        session['id_aluno'] = user['id']
                        destino = 'home_aluno'
                    
                    cursor.close()
                    conexao.close()
                    return redirect(url_for(destino))
                else:
                    print(f"DEBUG LOGIN: Senha incorreta.")
                    flash('Senha incorreta!', 'erro')
            else:
                print(f"DEBUG LOGIN: Usuário '{usuario}' não encontrado.")
                flash('Apelido não cadastrado!', 'erro')
                
        except Exception as e:
            print(f"DEBUG LOGIN: Erro: {e}")
            flash('Erro interno no sistema.', 'erro')
        finally:
            if conexao and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return render_template('usuario/login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        tipo = None
        
        if request.form.get('nomealuno'):
            tipo = 'aluno'
        elif request.form.get('nomeprof'):
            tipo = 'professor'
        else:
            flash('Tipo de usuário não identificado!', 'erro')
            return render_template('usuario/cadastro.html')
        
        if tipo == "professor":    
            nome_completo = request.form.get('nomeprof', '').strip()
            apelido = request.form.get('apelidoprof', '').strip()
            email1 = request.form.get('emailprof', '').strip()
            senha = request.form.get('senhaprof', '').strip()
            telefone = request.form.get('telefoneprof', '').strip()
            codigo = request.form.get('codigo_certificado', '').strip()
            espec = request.form.get('especializacoes', '').strip()
        elif tipo == 'aluno':
            nome_completo = request.form.get('nomealuno', '').strip()
            apelido = request.form.get('apelidoaluno', '').strip()
            email1 = request.form.get('emailaluno', '').strip()
            senha = request.form.get('senhaaluno', '').strip()
            telefone = request.form.get('telefonealuno', '').strip()
            codigo = None
            espec = ""
        
        campos_obrigatorios = [nome_completo, apelido, email1, senha, telefone]
        if not all(campos_obrigatorios):
            flash('Todos os campos obrigatórios devem ser preenchidos!', 'erro')
            return render_template('usuario/cadastro.html')
        
        # ADICIONAR VALIDAÇÃO DO EMAIL (FALTANDO!)
        if not validar_email(email1):
            flash("Email inválido!", "erro")
            return render_template('usuario/cadastro.html')
        
        conexao = conectar()
        if not conexao:
            flash("Erro de conexão com o banco de dados!", "erro")
            return render_template('usuario/cadastro.html')
        
        cursor = None
        try:
            cursor = conexao.cursor()  # ← DESCOMENTAR ESTA LINHA (NÃO PODE ESTAR COMENTADA!)
            print(f"DEBUG INSERT: nome={nome_completo}, apelido={apelido}, email={email1}, senha={senha}, tipo={tipo}")
            
            sql = """INSERT INTO usuarios 
                     (nome_completo, apelido, email, senha, telefone, tipo, codigo_diploma, expecializacoes) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            val = (nome_completo, apelido, email1, senha, telefone, tipo, codigo, espec)
            
            cursor.execute(sql, val)
            conexao.commit()
            usuario_id = cursor.lastrowid
            
            session['logado'] = True
            session['tipo'] = tipo
            session['usuario'] = nome_completo
            session['id'] = usuario_id
            
            if tipo == 'aluno':
                session['id_aluno'] = usuario_id
            else:
                session['id_professor'] = usuario_id
            
            flash('Conta criada com sucesso!', 'sucesso')
            return redirect(url_for('home_aluno' if tipo == 'aluno' else 'home_professor'))
                   
        except mysql.connector.Error as e:
            print(f"Erro detalhado: {e}")
            if conexao:
                conexao.rollback()
            
            flash('Erro ao cadastrar. Tente novamente.', 'erro')
            return render_template('usuario/cadastro.html')
        
        finally:
            if cursor:
                cursor.close()
            if conexao and conexao.is_connected():
                conexao.close()
    
    return render_template('usuario/cadastro.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('boas_vindas'))

# ==============================================================================
# ROTAS DO ALUNO
# ==============================================================================
@app.route('/home_aluno')
@login_required
def home_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_professor'))
    return render_template('aluno/home_aluno.html', usuario=session.get('usuario'))

@app.route('/cursos_aluno')
@login_required
def cursos_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    
    conexao = conectar()
    if not conexao:
        cursos = [
            {'id': 1, 'nome': 'Cálculo I', 'categoria': 'MATEMÁTICA', 
             'professor': 'Carlos', 'progresso': 75, 'cor': 'azul'},
            {'id': 2, 'nome': 'Python', 'categoria': 'DEV', 
             'professor': 'Ana', 'progresso': 90, 'cor': 'verde'}
        ]
        return render_template('aluno/cursos_aluno.html', cursos=cursos)
    
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.id, c.nome, c.categoria, 
                   u.nome_completo as professor,
                   COALESCE(
                       (SELECT COUNT(DISTINCT pa.capitulo_id) 
                        FROM progresso_aulas pa 
                        JOIN capitulos_curso cc ON pa.capitulo_id = cc.id
                        WHERE cc.curso_id = c.id AND pa.aluno_id = %s AND pa.completado = 1)
                       / NULLIF((SELECT COUNT(*) FROM capitulos_curso WHERE curso_id = c.id), 0) * 100,
                       0
                   ) as progresso,
                   CASE 
                       WHEN c.categoria = 'MATEMÁTICA' THEN 'azul'
                       WHEN c.categoria = 'DEV' THEN 'verde'
                       WHEN c.categoria = 'CIÊNCIAS' THEN 'vermelho'
                       ELSE 'laranja'
                   END as cor
            FROM cursos c
            LEFT JOIN usuarios u ON c.professor_id = u.id
            WHERE EXISTS (
                SELECT 1 FROM matricula m 
                WHERE m.curso_id = c.id AND m.aluno_id = %s
            )
        """, (session['id_aluno'], session['id_aluno']))
        
        cursos = cursor.fetchall()
        return render_template('aluno/cursos_aluno.html', cursos=cursos)
        
    except Exception as e:
        print(f"Erro ao buscar cursos: {e}")
        cursos = [
            {'id': 1, 'nome': 'Cálculo I', 'categoria': 'MATEMÁTICA', 
             'professor': 'Carlos', 'progresso': 75, 'cor': 'azul'}
        ]
        return render_template('aluno/cursos_aluno.html', cursos=cursos)
    finally:
        if conexao and conexao.is_connected():
            cursor.close()
            conexao.close()

# ==============================================================================
# ROTA PARA VER DETALHES DO CURSO - CORRIGIDA
# ==============================================================================
@app.route('/cursos/<int:curso_id>')
@login_required
def curso_detalhes(curso_id):
    """Página com todos os capítulos de um curso específico"""
    if session.get('tipo') != 'aluno':
        return redirect(url_for('home_aluno'))
    
    conexao = conectar()
    if not conexao:
        flash('Erro de conexão com o banco', 'erro')
        return redirect(url_for('cursos_aluno'))
    
    try:
        cursor = conexao.cursor(dictionary=True)
        
        # Buscar informações do curso
        cursor.execute("""
            SELECT c.id, c.nome as titulo, c.descricao, c.categoria, 
                   u.nome_completo as professor_nome
            FROM cursos c
            LEFT JOIN usuarios u ON c.professor_id = u.id
            WHERE c.id = %s
        """, (curso_id,))
        curso = cursor.fetchone()
        
        if not curso:
            flash('Curso não encontrado', 'erro')
            return redirect(url_for('cursos_aluno'))
        
        # Buscar capítulos do curso
        cursor.execute("""
            SELECT cc.*
            FROM capitulos_curso cc
            WHERE cc.curso_id = %s
            ORDER BY cc.ordem
        """, (curso_id,))
        capitulos = cursor.fetchall()
        
        # Para cada capítulo, buscar aulas e verificar se estão concluídas
        total_aulas_curso = 0
        total_aulas_concluidas_curso = 0
        capitulos_concluidos = 0
        
        for capitulo in capitulos:
            # Buscar aulas do capítulo
            cursor.execute("""
                SELECT a.*,
                       CASE 
                           WHEN EXISTS (SELECT 1 FROM progresso_aulas pa 
                                        WHERE pa.aula_id = a.id 
                                        AND pa.aluno_id = %s 
                                        AND pa.completado = 1) THEN 1
                           ELSE 0
                       END as concluida
                FROM aulas a
                WHERE a.capitulo_id = %s
                ORDER BY a.ordem
            """, (session['id_aluno'], capitulo['id']))
            
            aulas = cursor.fetchall()
            capitulo['aulas'] = aulas
            capitulo['total_aulas'] = len(aulas)
            
            # Contar aulas concluídas neste capítulo
            aulas_concluidas = sum(1 for aula in aulas if aula['concluida'] == 1)
            capitulo['aulas_concluidas'] = aulas_concluidas
            
            # Determinar se capítulo está concluído (todas as aulas concluídas)
            capitulo['concluido'] = aulas_concluidas == capitulo['total_aulas'] and capitulo['total_aulas'] > 0
            
            # Atualizar contadores gerais
            total_aulas_curso += capitulo['total_aulas']
            total_aulas_concluidas_curso += aulas_concluidas
            
            if capitulo['concluido']:
                capitulos_concluidos += 1
        
        total_capitulos = len(capitulos)
        progresso_geral = int((total_aulas_concluidas_curso / total_aulas_curso * 100)) if total_aulas_curso > 0 else 0
        
        return render_template('aluno/curso_detalhes.html',
                             curso=curso,
                             capitulos=capitulos,
                             progresso_geral=progresso_geral,
                             total_capitulos=total_capitulos,
                             capitulos_concluidos=capitulos_concluidos,
                             total_aulas_curso=total_aulas_curso,
                             total_aulas_concluidas_curso=total_aulas_concluidas_curso)
        
    except Exception as e:
        print(f"Erro ao buscar curso: {e}")
        flash('Erro ao carregar o curso', 'erro')
        return redirect(url_for('cursos_aluno'))
    finally:
        if conexao and conexao.is_connected():
            cursor.close()
            conexao.close()

# ==============================================================================
# ROTA PARA VER CAPÍTULO
# ==============================================================================
@app.route('/capitulo/<int:capitulo_id>')
@login_required
def ver_capitulo(capitulo_id):
    """Página de visualização de um capítulo específico"""
    if session.get('tipo') != 'aluno':
        return redirect(url_for('home_aluno'))
    
    conexao = conectar()
    if not conexao:
        flash('Erro de conexão com o banco', 'erro')
        return redirect(url_for('cursos_aluno'))
    
    try:
        cursor = conexao.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT cc.*, c.nome as curso_titulo, c.id as curso_id
            FROM capitulos_curso cc
            JOIN cursos c ON cc.curso_id = c.id
            WHERE cc.id = %s
        """, (capitulo_id,))
        capitulo = cursor.fetchone()
        
        if not capitulo:
            flash('Capítulo não encontrado', 'erro')
            return redirect(url_for('cursos_aluno'))
        
        cursor.execute("""
            SELECT a.*,
                   CASE 
                       WHEN EXISTS (SELECT 1 FROM progresso_aulas pa 
                                    WHERE pa.aula_id = a.id 
                                    AND pa.aluno_id = %s 
                                    AND pa.completado = 1) THEN 1
                       ELSE 0
                   END as assistida
            FROM aulas a
            WHERE a.capitulo_id = %s
            ORDER BY a.ordem
        """, (session['id_aluno'], capitulo_id))
        aulas = cursor.fetchall()
        
        cursor.execute("""
            SELECT id, titulo 
            FROM capitulos_curso 
            WHERE curso_id = %s AND ordem > %s
            ORDER BY ordem ASC
            LIMIT 1
        """, (capitulo['curso_id'], capitulo['ordem']))
        proximo_capitulo = cursor.fetchone()
        
        # Registrar acesso ao capítulo
        cursor.execute("""
            INSERT INTO progresso_aulas (aluno_id, capitulo_id, aula_id, completado, data_acesso)
            VALUES (%s, %s, NULL, 0, NOW())
            ON DUPLICATE KEY UPDATE data_acesso = NOW()
        """, (session['id_aluno'], capitulo_id))
        conexao.commit()
        
        return render_template('aluno/capitulo_detalhado.html',
                             capitulo=capitulo,
                             aulas=aulas,
                             proximo_capitulo=proximo_capitulo)
        
    except Exception as e:
        print(f"Erro ao buscar capítulo: {e}")
        flash('Erro ao carregar o capítulo', 'erro')
        return redirect(url_for('cursos_aluno'))
    finally:
        if conexao and conexao.is_connected():
            cursor.close()
            conexao.close()

# ==============================================================================
# ROTA PARA MARCAR/DESMARCAR AULA COMO COMPLETA - CORRIGIDA
# ==============================================================================
@app.route('/marcar_aula_completa', methods=['POST'])
@login_required
def marcar_aula_completa():
    """Marca ou desmarca uma aula como concluída"""
    if session.get('tipo') != 'aluno':
        return jsonify({'sucesso': False, 'erro': 'Acesso negado'}), 403
    
    conexao = None
    try:
        data = request.get_json()
        aula_id = data.get('aula_id')
        capitulo_id = data.get('capitulo_id')
        marcar = data.get('marcar', True)
        
        if not aula_id or not capitulo_id:
            return jsonify({'sucesso': False, 'erro': 'Dados incompletos'}), 400
        
        conexao = conectar()
        if not conexao:
            return jsonify({'sucesso': False, 'erro': 'Erro de conexão'}), 500
        
        cursor = conexao.cursor()
        
        # Buscar informações da aula para verificar se existe
        cursor.execute("SELECT id, capitulo_id FROM aulas WHERE id = %s", (aula_id,))
        aula_info = cursor.fetchone()
        
        if not aula_info:
            return jsonify({'sucesso': False, 'erro': 'Aula não encontrada'}), 404
        
        # Marcar/desmarcar aula
        if marcar:
            # Marcar aula como concluída
            cursor.execute("""
                INSERT INTO progresso_aulas (aluno_id, capitulo_id, aula_id, completado, data_conclusao)
                VALUES (%s, %s, %s, 1, NOW())
                ON DUPLICATE KEY UPDATE completado = 1, data_conclusao = NOW()
            """, (session['id_aluno'], capitulo_id, aula_id))
        else:
            # Desmarcar aula
            cursor.execute("""
                DELETE FROM progresso_aulas 
                WHERE aluno_id = %s AND capitulo_id = %s AND aula_id = %s
            """, (session['id_aluno'], capitulo_id, aula_id))
        
        # Buscar curso_id para atualizações
        cursor.execute("SELECT curso_id FROM capitulos_curso WHERE id = %s", (capitulo_id,))
        curso_info = cursor.fetchone()
        curso_id = curso_info[0] if curso_info else None
        
        # Calcular progresso do capítulo
        cursor.execute("""
            SELECT 
                COUNT(*) as total_aulas,
                COUNT(CASE WHEN pa.completado = 1 THEN 1 END) as concluidas
            FROM aulas a
            LEFT JOIN progresso_aulas pa ON a.id = pa.aula_id AND pa.aluno_id = %s
            WHERE a.capitulo_id = %s
        """, (session['id_aluno'], capitulo_id))
        
        cap_result = cursor.fetchone()
        total_aulas_cap = cap_result[0]
        concluidas_cap = cap_result[1] or 0
        
        capitulo_concluido = concluidas_cap == total_aulas_cap and total_aulas_cap > 0
        percentual_cap = int((concluidas_cap / total_aulas_cap * 100)) if total_aulas_cap > 0 else 0
        
        # Atualizar status do capítulo
        if capitulo_concluido:
            cursor.execute("""
                INSERT INTO progresso_aulas (aluno_id, capitulo_id, completado, data_conclusao)
                VALUES (%s, %s, 1, NOW())
                ON DUPLICATE KEY UPDATE completado = 1, data_conclusao = NOW()
            """, (session['id_aluno'], capitulo_id))
        
        # Calcular progresso do curso
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT cc.id) as total_capitulos,
                COUNT(DISTINCT CASE WHEN pa.completado = 1 THEN pa.capitulo_id END) as capitulos_concluidos,
                COUNT(DISTINCT a.id) as total_aulas,
                COUNT(DISTINCT CASE WHEN pa2.completado = 1 THEN pa2.aula_id END) as aulas_concluidas
            FROM cursos c
            LEFT JOIN capitulos_curso cc ON c.id = cc.curso_id
            LEFT JOIN aulas a ON cc.id = a.capitulo_id
            LEFT JOIN progresso_aulas pa ON cc.id = pa.capitulo_id AND pa.aluno_id = %s AND pa.aula_id IS NULL
            LEFT JOIN progresso_aulas pa2 ON a.id = pa2.aula_id AND pa2.aluno_id = %s
            WHERE c.id = %s
            GROUP BY c.id
        """, (session['id_aluno'], session['id_aluno'], curso_id))
        
        curso_result = cursor.fetchone()
        
        if curso_result:
            total_capitulos_curso = curso_result[0]
            capitulos_concluidos_curso = curso_result[1] or 0
            total_aulas_curso = curso_result[2]
            aulas_concluidas_curso = curso_result[3] or 0
            
            curso_concluido = capitulos_concluidos_curso == total_capitulos_curso and total_capitulos_curso > 0
            percentual_curso = int((aulas_concluidas_curso / total_aulas_curso * 100)) if total_aulas_curso > 0 else 0
        else:
            total_capitulos_curso = 0
            capitulos_concluidos_curso = 0
            total_aulas_curso = 0
            aulas_concluidas_curso = 0
            curso_concluido = False
            percentual_curso = 0
        
        conexao.commit()
        
        return jsonify({
            'sucesso': True,
            'marcado': marcar,
            'progresso_capitulo': {
                'total_aulas': total_aulas_cap,
                'concluidas': concluidas_cap,
                'percentual': percentual_cap,
                'capitulo_concluido': capitulo_concluido
            },
            'progresso_curso': {
                'curso_id': curso_id,
                'total_capitulos': total_capitulos_curso,
                'capitulos_concluidos': capitulos_concluidos_curso,
                'total_aulas': total_aulas_curso,
                'aulas_concluidas': aulas_concluidas_curso,
                'percentual': percentual_curso,
                'curso_concluido': curso_concluido
            }
        })
        
    except Exception as e:
        print(f"Erro ao marcar/desmarcar aula: {e}")
        if conexao:
            conexao.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        if conexao and conexao.is_connected():
            conexao.close()

# ==============================================================================
# OUTRAS ROTAS DO ALUNO
# ==============================================================================
@app.route('/perfil_aluno')
@login_required
def perfil_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    
    aluno_id = session.get('id_aluno')
    conexao = conectar()
    aluno = None
    stats = None
    
    if conexao:
        try:
            cursor = conexao.cursor(dictionary=True)
            
            # Buscar dados reais do aluno
            cursor.execute("""
                SELECT id, nome_completo, apelido, email, telefone 
                FROM usuarios 
                WHERE id = %s AND tipo = 'aluno'
            """, (aluno_id,))
            aluno = cursor.fetchone()
            
            # Buscar estatísticas do aluno (exemplo - adapte conforme seu banco)
            cursor.execute("""
                SELECT 
                    COALESCE(AVG(n.nota), 0) as media_geral,
                    COUNT(DISTINCT CASE WHEN pa.completado = 1 THEN pa.aula_id END) * 100.0 / 
                    NULLIF(COUNT(DISTINCT a.id), 0) as frequencia
                FROM usuarios u
                LEFT JOIN matricula m ON u.id = m.aluno_id
                LEFT JOIN notas n ON m.curso_id = n.curso_id AND u.id = n.aluno_id
                LEFT JOIN progresso_aulas pa ON u.id = pa.aluno_id
                LEFT JOIN aulas a ON pa.aula_id = a.id
                WHERE u.id = %s
                GROUP BY u.id
            """, (aluno_id,))
            
            stats_result = cursor.fetchone()
            if stats_result:
                stats = {
                    'media_geral': round(stats_result['media_geral'], 1) if stats_result['media_geral'] else 0,
                    'frequencia': round(stats_result['frequencia'], 0) if stats_result['frequencia'] else 0
                }
            else:
                stats = {'media_geral': 0, 'frequencia': 0}
                
        except Exception as e:
            print(f"Erro ao buscar perfil do aluno: {e}")
        finally:
            if conexao and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    # Se não encontrou no banco, usar dados mínimos
    if not aluno:
        aluno = {
            'nome_completo': session.get('usuario', 'Aluno'),
            'email': 'Não cadastrado',
            'id': aluno_id
        }
    
    if not stats:
        stats = {'media_geral': 0, 'frequencia': 0}
    
    return render_template('aluno/perfil_aluno.html', aluno=aluno, estatisticas=stats)

@app.route('/calendario_aluno')
@login_required
def calendario_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    eventos = [{'titulo': 'Prova', 'dia': 15, 'mes': 11, 'ano': 2024}]
    return render_template('aluno/calendario_aluno.html', eventos=eventos)

@app.route('/desempenho_aluno')
@login_required
def desempenho_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    
    dados = {'media_geral': 8.5}
    
    # ADICIONE ESTAS LINHAS:
    aluno = {
        'apelido': session.get('usuario', 'Aluno'),
        'nome': session.get('usuario', 'Aluno'),
        'id': session.get('id_aluno')
    }
    
    # CORRIJA O RETURN:
    return render_template('aluno/desempenho_aluno.html', 
                          dados=dados,
                          aluno=aluno)  # ← ADICIONE 'aluno' AQUI

@app.route('/notificacoes_aluno')
@login_required
def notificacoes_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    notificacoes = [{'titulo': 'Bem-vindo', 'descricao': 'Sistema atualizado', 'lida': False}]
    return render_template('aluno/notificacoes_aluno.html', notificacoes=notificacoes, notificacoes_nao_lidas=notificacoes)


# ==============================================================================

@app.route('/editar_perfil_aluno', methods=['GET', 'POST'])
@login_required
def editar_perfil_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    
    aluno_id = session.get('id_aluno')
    
    # Se for POST (salvar dados)
    if request.method == 'POST':
        nome = request.form.get('nome_completo', '').strip()
        email = request.form.get('email', '').strip()
        telefone = request.form.get('telefone', '').strip()
        senha_atual = request.form.get('senha_atual', '').strip()
        nova_senha = request.form.get('nova_senha', '').strip()
        confirmar_senha = request.form.get('confirmar_senha', '').strip()
        foto_base64 = request.form.get('foto_perfil', '').strip()
        
        # Processar foto se houver
        foto_processada = None
        if foto_base64 and foto_base64.startswith('data:image'):
            try:
                # Extrair a parte base64
                header, encoded = foto_base64.split(',', 1)
                # Decodificar e converter para string para salvar no banco
                foto_processada = encoded  # Salva apenas o base64 sem o header
            except:
                pass
        
        # Verificar se quer alterar senha
        alterar_senha = False
        
        # Se preencheu algum campo de senha
        if senha_atual or nova_senha or confirmar_senha:
            if not senha_atual:
                flash('Digite sua senha atual para alterar a senha', 'erro')
                return redirect(url_for('editar_perfil_aluno'))
            
            if not nova_senha:
                flash('Digite a nova senha', 'erro')
                return redirect(url_for('editar_perfil_aluno'))
            
            if not confirmar_senha:
                flash('Confirme a nova senha', 'erro')
                return redirect(url_for('editar_perfil_aluno'))
            
            if nova_senha != confirmar_senha:
                flash('As novas senhas não coincidem', 'erro')
                return redirect(url_for('editar_perfil_aluno'))
            
            if len(nova_senha) < 4:
                flash('A nova senha deve ter pelo menos 4 caracteres', 'erro')
                return redirect(url_for('editar_perfil_aluno'))
            
            alterar_senha = True
        
        conexao = conectar()
        if conexao:
            try:
                cursor = conexao.cursor(dictionary=True)
                
                # Verificar senha atual se for alterar senha
                if alterar_senha:
                    cursor.execute("SELECT senha FROM usuarios WHERE id = %s", (aluno_id,))
                    aluno_db = cursor.fetchone()
                    
                    if not aluno_db or aluno_db['senha'] != senha_atual:
                        flash('Senha atual incorreta', 'erro')
                        conexao.close()
                        return redirect(url_for('editar_perfil_aluno'))
                
                # Atualizar dados
                if alterar_senha and foto_processada:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET nome_completo = %s, email = %s, telefone = %s, 
                            senha = %s, foto_perfil = %s
                        WHERE id = %s
                    """, (nome, email, telefone, nova_senha, foto_processada, aluno_id))
                elif alterar_senha:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET nome_completo = %s, email = %s, telefone = %s, 
                            senha = %s
                        WHERE id = %s
                    """, (nome, email, telefone, nova_senha, aluno_id))
                elif foto_processada:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET nome_completo = %s, email = %s, telefone = %s, 
                            foto_perfil = %s
                        WHERE id = %s
                    """, (nome, email, telefone, foto_processada, aluno_id))
                else:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET nome_completo = %s, email = %s, telefone = %s
                        WHERE id = %s
                    """, (nome, email, telefone, aluno_id))
                
                conexao.commit()
                
                # Atualiza nome na sessão
                session['usuario'] = nome
                
                # Atualiza foto na sessão se foi alterada
                if foto_processada:
                    session['foto_perfil'] = f"data:image/jpeg;base64,{foto_processada}"
                
                flash('Perfil atualizado com sucesso!', 'sucesso')
                
            except mysql.connector.Error as e:
                conexao.rollback()
                if e.errno == 1062:  # Erro de duplicação (email duplicado)
                    flash('Este email já está em uso por outro usuário', 'erro')
                else:
                    flash(f'Erro ao atualizar: {e}', 'erro')
            except Exception as e:
                flash(f'Erro: {e}', 'erro')
            finally:
                conexao.close()
        
        return redirect(url_for('perfil_aluno'))
    
    # Se for GET (mostrar formulário)
    conexao = conectar()
    aluno = None
    
    if conexao:
        try:
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (aluno_id,))
            aluno = cursor.fetchone()
            
            # Se houver foto no banco, adicionar o prefixo data URL
            if aluno and aluno.get('foto_perfil'):
                aluno['foto_perfil'] = f"data:image/jpeg;base64,{aluno['foto_perfil']}"
                
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            conexao.close()
    
    # Se não achou aluno, cria um básico
    if not aluno:
        aluno = {
            'id': aluno_id,
            'nome_completo': session.get('usuario', 'Aluno'),
            'email': 'email@teste.com',
            'telefone': '',
            'apelido': session.get('usuario', 'aluno'),
            'foto_perfil': None
        }
    
    return render_template('aluno/editar_perfil_aluno.html', aluno=aluno)

@app.route('/configuracoes_aluno')
@login_required
def configuracoes_aluno():
    if session.get('tipo') != 'aluno': 
        return redirect(url_for('home_aluno'))
    configuracoes = session.get('configuracoes', CONFIGURACOES_PADRAO)
    return render_template('aluno/configuracoes_aluno.html', configuracoes=configuracoes)

@app.route('/configuracoes/salvar', methods=['POST'])
@login_required
def salvar_configuracoes_ajax():
    try:
        aluno_id = session.get('id_aluno')
        dados = request.get_json()
        if not dados: 
            return jsonify({'sucesso': False}), 400
        
        config_atual = session.get('configuracoes', CONFIGURACOES_PADRAO.copy())
        
        for k, v in dados.items():
            if k in CONFIGURACOES_PADRAO:
                if k in ['tempo_sessao', 'tamanho_fonte']:
                    try: 
                        config_atual[k] = float(v) if '.' in str(v) else int(v)
                    except: 
                        pass
                elif isinstance(CONFIGURACOES_PADRAO[k], bool):
                    config_atual[k] = bool(v)
                else:
                    config_atual[k] = str(v)
        
        if salvar_configuracoes_banco(aluno_id, 'aluno', config_atual):
            session['configuracoes'] = config_atual
            return jsonify({'sucesso': True})
        return jsonify({'sucesso': False}), 500
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/aplicar_configuracoes')
def aplicar_configuracoes():
    config = session.get('configuracoes', CONFIGURACOES_PADRAO) if session.get('logado') else CONFIGURACOES_PADRAO
    js = f"""
    document.addEventListener('DOMContentLoaded', () => {{
        if('{config.get("tema_sistema")}' === 'escuro') document.documentElement.setAttribute('data-tema', 'escuro');
        document.documentElement.style.fontSize = '{config.get("tamanho_fonte", 1.0) * 100}%';
        if({'true' if config.get("alto_contraste") else 'false'}) document.body.classList.add('alto-contraste');
    }});
    """
    resp = make_response(js)
    resp.headers['Content-Type'] = 'application/javascript'
    return resp

# ==============================================================================
# ROTAS DO PROFESSOR
# ==============================================================================
@app.route('/home_professor')
def home_professor():
    if not session.get('logado') or session.get('tipo') != 'professor':
        return redirect(url_for('login'))
    return render_template('professor/home_professor.html', usuario=session.get('usuario'))

@app.route('/professor/alunos')
def lista_alunos():
    alunos = [...] 
    return render_template('professor/lista_alunos.html', alunos=alunos)

@app.route('/professor/aluno/<int:id>')
def visualizar_aluno(id):
    aluno = {
        'id': id,
        'nome_completo': f'Aluno Teste {id}',
        'apelido': f'Apelido {id}',
        'email': f'aluno{id}@teste.com',
        'telefone': '(11) 99999-9999',
    }
    return render_template('professor/visualizar_aluno.html', aluno=aluno)

# ==============================================================================
# INICIALIZAÇÃO
# ==============================================================================
if __name__ == '__main__':
    conexao = conectar()
    if conexao:
        try:
            cursor = conexao.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    tipo_usuario ENUM('aluno', 'professor') NOT NULL,
                    config_json JSON,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_usuario_config (usuario_id, tipo_usuario)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS atividades_usuario (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    tipo_usuario ENUM('aluno', 'professor') NOT NULL,
                    tipo_atividade VARCHAR(50) NOT NULL,
                    descricao TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conexao.commit()
        except: 
            pass
        finally:
            if conexao.is_connected(): 
                cursor.close()
                conexao.close()
    
@app.route('/seus_cursos')
@login_required
def seus_cursos():
    """Página principal dos cursos do professor"""
    if session.get('tipo') != 'professor':
        return redirect(url_for('home_aluno'))
    
    # Dados fictícios dos cursos
    cursos = [
        {
            'id': 1,
            'nome': 'Python',
            'categoria': 'PROGRAMAÇÃO',
            'professor': 'tarzan',
            'alunos': 0,
            'atividades': 8,
            'progresso': 0,
            'cor': 'roxo'
        },
        {
            'id': 2,
            'nome': 'Cálculo I',
            'categoria': 'MATEMÁTICA',
            'professor': 'tarzan',
            'alunos': 0,
            'atividades': 12,
            'progresso': 0,
            'cor': 'azul'
        },
        {
            'id': 3,
            'nome': 'Banco de Dados',
            'categoria': 'TI',
            'professor': 'tarzan',
            'alunos': 0,
            'atividades': 6,
            'progresso': 0,
            'cor': 'verde'
        },
        {
            'id': 4,
            'nome': 'Web Design',
            'categoria': 'DESIGN',
            'professor': 'tarzan',
            'alunos': 0,
            'atividades': 7,
            'progresso': 0,
            'cor': 'laranja'
        }
    ]
    
    return render_template(
        'professor/seus_cursos.html',
        cursos=cursos
    )
@app.route('/acessar_curso/<int:curso_id>')
@login_required
def acessar_curso(curso_id):
    """Página de acesso ao curso para professores"""
    if session.get('tipo') != 'professor':
        return redirect(url_for('home_aluno'))
    
    # Buscar dados do curso do banco de dados
    conexao = conectar()
    curso = None
    stats = None
    modulos = []
    
    if conexao:
        try:
            cursor = conexao.cursor(dictionary=True)
            
            # Buscar curso específico do professor
            cursor.execute("""
                SELECT c.*, u.nome_completo as professor_nome 
                FROM cursos c
                LEFT JOIN usuarios u ON c.professor_id = u.id
                WHERE c.id = %s AND c.professor_id = %s
            """, (curso_id, session['id_professor']))
            curso = cursor.fetchone()
            
            if not curso:
                flash('Curso não encontrado ou acesso não autorizado', 'erro')
                return redirect(url_for('seus_cursos'))
            
            # Buscar estatísticas do curso
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT m.aluno_id) as total_alunos,
                    COUNT(DISTINCT a.id) as total_aulas,
                    COALESCE(AVG(n.nota), 0) as media_turma,
                    COUNT(DISTINCT CASE WHEN pa.completado = 1 THEN pa.aula_id END) as aulas_concluidas_total
                FROM cursos c
                LEFT JOIN matricula m ON c.id = m.curso_id
                LEFT JOIN capitulos_curso cc ON c.id = cc.curso_id
                LEFT JOIN aulas a ON cc.id = a.capitulo_id
                LEFT JOIN progresso_aulas pa ON a.id = pa.aula_id
                LEFT JOIN notas n ON c.id = n.curso_id
                WHERE c.id = %s
                GROUP BY c.id
            """, (curso_id,))
            
            stats = cursor.fetchone()
            
            if not stats:
                stats = {
                    'total_alunos': 0,
                    'total_aulas': 0,
                    'media_turma': 0,
                    'aulas_concluidas_total': 0
                }
            
            # Buscar módulos/capítulos do curso
            cursor.execute("""
                SELECT cc.*, 
                       COUNT(a.id) as total_aulas_modulo,
                       COUNT(CASE WHEN pa.completado = 1 THEN pa.aula_id END) as aulas_concluidas_modulo
                FROM capitulos_curso cc
                LEFT JOIN aulas a ON cc.id = a.capitulo_id
                LEFT JOIN progresso_aulas pa ON a.id = pa.aula_id
                WHERE cc.curso_id = %s
                GROUP BY cc.id
                ORDER BY cc.ordem
            """, (curso_id,))
            
            modulos = cursor.fetchall()
            
        except Exception as e:
            print(f"Erro ao buscar curso: {e}")
            flash('Erro ao carregar o curso', 'erro')
            return redirect(url_for('seus_cursos'))
        finally:
            if conexao and conexao.is_connected():
                cursor.close()
                conexao.close()
    else:
        # Dados de exemplo se não houver conexão
        curso = {
            'id': curso_id,
            'nome': f'Curso {curso_id}',
            'descricao': 'Descrição do curso para o professor.',
            'professor_nome': session.get('usuario', 'Professor'),
            'categoria': 'PROGRAMAÇÃO'
        }
        
        stats = {
            'total_alunos': 25,
            'total_aulas': 30,
            'media_turma': 8.5,
            'aulas_concluidas_total': 22
        }
        
        modulos = [
            {'titulo': 'Módulo 1: Introdução', 'concluido': True, 'total_aulas_modulo': 5, 'aulas_concluidas_modulo': 5},
            {'titulo': 'Módulo 2: Conceitos Básicos', 'concluido': True, 'total_aulas_modulo': 6, 'aulas_concluidas_modulo': 6},
            {'titulo': 'Módulo 3: Tópicos Avançados', 'concluido': False, 'total_aulas_modulo': 4, 'aulas_concluidas_modulo': 2}
        ]
    
    # Calcular progresso
    if stats and stats['total_aulas'] and stats['total_aulas'] > 0:
        progresso = int((stats['aulas_concluidas_total'] / stats['total_aulas']) * 100)
    else:
        progresso = 0
    
    # Renderizar o template com o layout base do professor
    return render_template(
        'professor/acessar_curso.html',  # ← MUDADO AQUI: usa o template que estende base_professor
        curso=curso,
        stats=stats,
        modulos=modulos,
        progresso=progresso
    )

# ==============================================================================
# ROTA DE DETALHES DO CURSO - PROFESSOR (DESIGN ESPECÍFICO) - SOMENTE DADOS FICTÍCIOS
# ==============================================================================
@app.route('/detalhes_cursos_professor/<int:curso_id>')
@login_required
def detalhes_cursos_professor(curso_id):
    """Página de detalhes do curso para professor (com dados fictícios)"""
    if session.get('tipo') != 'professor':
        return redirect(url_for('home_aluno'))
    
    # Dados fictícios para diferentes cursos baseados no curso_id
    cursos_data = {
        1: {  # Python
            'id': 1,
            'nome': 'Python',
            'descricao': 'Curso completo de programação em Python',
            'categoria': 'PROGRAMAÇÃO',
            'professor': 'tarzan',
            'alunos': 24,
            'atividades': 8,
            'progresso': 85,
            'media_turma': 8.5
        },
        2: {  # Cálculo I
            'id': 2,
            'nome': 'Cálculo I',
            'descricao': 'Curso de cálculo diferencial e integral',
            'categoria': 'MATEMÁTICA',
            'professor': 'tarzan',
            'alunos': 32,
            'atividades': 12,
            'progresso': 65,
            'media_turma': 7.8
        },
        3: {  # Banco de Dados
            'id': 3,
            'nome': 'Banco de Dados',
            'descricao': 'Fundamentos de bancos de dados relacionais',
            'categoria': 'TI',
            'professor': 'tarzan',
            'alunos': 18,
            'atividades': 6,
            'progresso': 90,
            'media_turma': 9.0
        },
        4: {  # Web Design
            'id': 4,
            'nome': 'Web Design',
            'descricao': 'Design e desenvolvimento de websites',
            'categoria': 'DESIGN',
            'professor': 'tarzan',
            'alunos': 21,
            'atividades': 7,
            'progresso': 75,
            'media_turma': 8.2
        }
    }
    
    # Verifica se o curso_id existe nos dados fictícios
    if curso_id not in cursos_data:
        flash('Curso não encontrado', 'erro')
        return redirect(url_for('seus_cursos'))
    
    curso = cursos_data[curso_id]
    
    # Alunos fictícios - ajustar quantidade baseada no curso
    base_alunos = [
        {
            'id': 1,
            'nome_completo': 'Ana Maria Silva',
            'apelido': 'Ana',
            'email': 'ana.maria@email.com',
            'progresso': 92,
            'media_aluno': 9.2,
            'ultimo_acesso': 'Hoje, 14:30',
            'atividades_concluidas': 8
        },
        {
            'id': 2,
            'nome_completo': 'Carlos Roberto Santos',
            'apelido': 'Carlos',
            'email': 'carlos.roberto@email.com',
            'progresso': 75,
            'media_aluno': 8.5,
            'ultimo_acesso': 'Ontem, 20:15',
            'atividades_concluidas': 6
        },
        {
            'id': 3,
            'nome_completo': 'Mariana Ferreira',
            'apelido': 'Mariana',
            'email': 'mariana.ferreira@email.com',
            'progresso': 100,
            'media_aluno': 9.5,
            'ultimo_acesso': 'Hoje, 10:45',
            'atividades_concluidas': 8
        },
        {
            'id': 4,
            'nome_completo': 'João Oliveira',
            'apelido': 'João',
            'email': 'joao.oliveira@email.com',
            'progresso': 62,
            'media_aluno': 7.8,
            'ultimo_acesso': '3 dias atrás',
            'atividades_concluidas': 5
        },
        {
            'id': 5,
            'nome_completo': 'Patrícia Costa',
            'apelido': 'Patrícia',
            'email': 'patricia.costa@email.com',
            'progresso': 42,
            'media_aluno': 6.5,
            'ultimo_acesso': '1 semana atrás',
            'atividades_concluidas': 4
        }
    ]
    
    # Para cursos com mais alunos, adicionar mais alunos fictícios
    if curso['alunos'] > 5:
        alunos_extras = [
            {
                'id': 6,
                'nome_completo': 'Ricardo Almeida',
                'apelido': 'Ricardo',
                'email': 'ricardo.almeida@email.com',
                'progresso': 83, 
                'media_aluno': 8.8,
                'ultimo_acesso': 'Hoje, 09:15',
                'atividades_concluidas': 7
            },
            {
                'id': 7,
                'nome_completo': 'Fernanda Lima',
                'apelido': 'Fernanda',
                'email': 'fernanda.lima@email.com',
                'progresso': 96,
                'media_aluno': 9.3,
                'ultimo_acesso': 'Hoje, 11:30',
                'atividades_concluidas': 8
            },
            {
                'id': 8,
                'nome_completo': 'Pedro Santos',
                'apelido': 'Pedro',
                'email': 'pedro.santos@email.com',
                'progresso': 67,
                'media_aluno': 8.0,
                'ultimo_acesso': '2 dias atrás',
                'atividades_concluidas': 6
            }
        ]
        alunos = base_alunos + alunos_extras
    else:
        alunos = base_alunos
    
    # Ajustar número de alunos baseado no curso
    alunos = alunos[:curso['alunos']]
    
    # Atividades fictícias - ajustar quantidade baseada no curso
    base_atividades = [
        {
            'id': 1,
            'titulo': 'Introdução',
            'descricao': 'Conceitos básicos',
            'capitulo_titulo': 'Módulo 1',
            'data_criacao': '15/03/2023',
            'alunos_concluidos': 24,
            'total_alunos_curso': 24,
            'percentual_conclusao': 100,
            'media_atividade': 9.0,
            'status': 'concluida'
        },
        {
            'id': 2,
            'titulo': 'Conceitos Fundamentais',
            'descricao': 'Fundamentos da disciplina',
            'capitulo_titulo': 'Módulo 1',
            'data_criacao': '22/03/2023',
            'alunos_concluidos': 24,
            'total_alunos_curso': 24,
            'percentual_conclusao': 100,
            'media_atividade': 8.8,
            'status': 'concluida'
        },
        {
            'id': 3,
            'titulo': 'Tópicos Intermediários',
            'descricao': 'Conceitos intermediários',
            'capitulo_titulo': 'Módulo 2',
            'data_criacao': '29/03/2023',
            'alunos_concluidos': 22,
            'total_alunos_curso': 24,
            'percentual_conclusao': 92,
            'media_atividade': 8.5,
            'status': 'concluida'
        },
        {
            'id': 4,
            'titulo': 'Aplicações Práticas',
            'descricao': 'Exemplos práticos',
            'capitulo_titulo': 'Módulo 2',
            'data_criacao': '05/04/2023',
            'alunos_concluidos': 20,
            'total_alunos_curso': 24,
            'percentual_conclusao': 83,
            'media_atividade': 8.2,
            'status': 'concluida'
        },
        {
            'id': 5,
            'titulo': 'Técnicas Avançadas',
            'descricao': 'Conceitos avançados',
            'capitulo_titulo': 'Módulo 3',
            'data_criacao': '12/04/2023',
            'alunos_concluidos': 18,
            'total_alunos_curso': 24,
            'percentual_conclusao': 75,
            'media_atividade': 7.9,
            'status': 'em_andamento'
        },
        {
            'id': 6,
            'titulo': 'Projeto Prático',
            'descricao': 'Desenvolvimento de projeto',
            'capitulo_titulo': 'Módulo 4',
            'data_criacao': '19/04/2023',
            'alunos_concluidos': 12,
            'total_alunos_curso': 24,
            'percentual_conclusao': 50,
            'media_atividade': 7.0,
            'status': 'em_andamento'
        }
    ]
    
    # Ajustar atividades baseado no curso
    atividades = base_atividades[:curso['atividades']]
    
    # Estatísticas do curso
    stats = {
        'total_alunos': curso['alunos'],
        'total_atividades': curso['atividades'],
        'media_turma': curso['media_turma'],
        'aulas_concluidas_total': curso['progresso']
    }
    
    # Renderizar o template com dados específicos do curso
    return render_template(
        'professor/detalhes_cursos_professor.html',
        curso=curso,
        stats=stats,
        alunos=alunos,
        atividades=atividades,
        progresso=curso['progresso']
    )
@app.route('/curso/python')
@login_required
def curso_python():
    """Página específica do curso de Python"""
    if session.get('tipo') != 'professor':
        return redirect(url_for('home_aluno'))
    
    # Dados do curso Python
    curso_python = {
        'nome': 'Python',
        'descricao': 'Curso completo de programação Python para iniciantes e intermediários.',
        'professor': session.get('usuario', 'Professor'),
        'alunos_ativos': 24,
        'total_aulas': 30,
        'aulas_concluidas': 22,
        'proxima_aula': 'Funções Avançadas e Lambdas',
        'data_proxima_aula': '15/12/2024',
        'atividades_pendentes': 3,
        'media_turma': 8.5
    }
    
    # Módulos do curso
    modulos = [
        {'titulo': 'Introdução ao Python', 'concluido': True, 'aulas': 5},
        {'titulo': 'Estruturas de Dados', 'concluido': True, 'aulas': 6},
        {'titulo': 'Funções e Módulos', 'concluido': True, 'aulas': 4},
        {'titulo': 'Programação Orientada a Objetos', 'concluido': True, 'aulas': 5},
        {'titulo': 'Manipulação de Arquivos', 'concluido': False, 'aulas': 4},
        {'titulo': 'Bibliotecas Avançadas', 'concluido': False, 'aulas': 6}
    ]
    
    return render_template(
        'professor/curso_python.html',
        professor_nome=session.get('usuario', 'Professor'),
        curso=curso_python,
        modulos=modulos
    )    

@app.route('/calendario_professor')
@login_required
def calendario_professor():
    if session.get('tipo') != 'professor':
        return redirect(url_for('home_aluno'))
    # Você pode carregar eventos do banco de dados aqui
    return render_template('professor/calendario_professor.html')

# @app.route('/perfil_professor')
# @login_required
# def perfil_professor():
#     if session.get('tipo') != 'professor':
#         return redirect(url_for('home_aluno'))
    
#     # Aqui você pode carregar dados reais do professor do banco de dados
#     return render_template('professor/perfil_professor.html')
    
@app.route('/perfil_professor')
@login_required
def perfil_professor():
    """Exibe a página de perfil do professor"""
    if session.get('tipo') != 'professor':
        return redirect(url_for('home_aluno'))
    
    # Carrega dados do professor do banco de dados
    conexao = conectar()
    if conexao:
        try:
            cursor = conexao.cursor(dictionary=True)
            professor_id = session.get('id_professor')
            
            # Busca informações do professor
            cursor.execute("""
                SELECT nome_completo, email, telefone, tipo, codigo_diploma as expecializacao, 
                       DATE_FORMAT(criado_em, '%d/%m/%Y') as data_cadastro
                FROM usuarios 
                WHERE id = %s
            """, (professor_id,))
            professor = cursor.fetchone()
            
            # Busca estatísticas
            cursor.execute("SELECT COUNT(*) as total_cursos FROM cursos WHERE professor_id = %s", (professor_id,))
            total_cursos = cursor.fetchone()['total_cursos'] or 0
            
            # Busca total de alunos (supondo que haja uma tabela matricula)
            cursor.execute("""
                SELECT COUNT(DISTINCT aluno_id) as total_alunos 
                FROM matriculas 
                WHERE curso_id IN (SELECT id FROM cursos WHERE professor_id = %s)
            """, (professor_id,))
            total_alunos = cursor.fetchone()['total_alunos'] or 0
            
            # Dados de exemplo para aulas e avaliação (ajuste conforme sua estrutura)
            total_aulas = 156  # Substitua por consulta real
            avaliacao = 4.8    # Substitua por consulta real
            
            # Busca especializações
            cursor.execute("SELECT expecializacoes FROM usuarios WHERE id = %s", (professor_id,))
            especializacoes_result = cursor.fetchone()
            especializacoes = []
            
            if especializacoes_result and especializacoes_result['expecializacoes']:
                especializacoes = [esp.strip() for esp in especializacoes_result['expecializacoes'].split(',') if esp.strip()]
            
        except Exception as e:
            print(f"Erro ao carregar perfil: {e}")
            professor = None
            total_cursos = 0
            total_alunos = 0
            total_aulas = 156
            avaliacao = 4.8
            especializacoes = ['Matemática', 'Física', 'Programação', 'Educação Online']
        finally:
            if conexao.is_connected():
                cursor.close()
                conexao.close()
    
    # Se não encontrou dados, usa valores padrão
    if not professor:
        professor = {
            'nome_completo': session.get('usuario', 'Professor'),
            'email': 'professor@escola.com',
            'telefone': '(11) 99999-9999',
            'formacao': 'Mestre em Educação',
            'data_cadastro': '01/01/2024'
        }
    
    return render_template('professor/perfil_professor.html',
                         professor=professor,
                         total_cursos=total_cursos,
                         total_alunos=total_alunos,
                         total_aulas=total_aulas,
                         avaliacao=avaliacao,
                         especializacoes=especializacoes)


@app.route('/perfil_professor/editar', methods=['POST'])
@login_required
def editar_perfil_professor():
    """Processa a edição do perfil do professor"""
    if session.get('tipo') != 'professor':
        return jsonify({'sucesso': False, 'erro': 'Acesso não autorizado'}), 403
    
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({'sucesso': False, 'erro': 'Dados não recebidos'}), 400
        
        professor_id = session.get('id_professor')
        
        # Validação dos dados
        campos_editaveis = ['email', 'telefone']
        campos_para_atualizar = {}
        
        for campo in campos_editaveis:
            if campo in dados and dados[campo]:
                campos_para_atualizar[campo] = dados[campo]
        
        # Trata especializações separadamente
        if 'formacao' in dados and dados['formacao']:
            campos_para_atualizar['expecializacoes'] = dados['formacao']
        
        # Validação de email
        if 'email' in campos_para_atualizar:
            if not validar_email(campos_para_atualizar['email']):
                return jsonify({'sucesso': False, 'erro': 'Email inválido'}), 400
            
            # Verifica se email já existe (excluindo o próprio usuário)
            conexao = conectar()
            if conexao:
                cursor = conexao.cursor()
                cursor.execute("SELECT id FROM usuarios WHERE email = %s AND id != %s", 
                             (campos_para_atualizar['email'], professor_id))
                if cursor.fetchone():
                    cursor.close()
                    conexao.close()
                    return jsonify({'sucesso': False, 'erro': 'Este email já está em uso'}), 400
        
        # Atualiza no banco de dados
        if campos_para_atualizar:
            conexao = conectar()
            if not conexao:
                return jsonify({'sucesso': False, 'erro': 'Erro de conexão com o banco'}), 500
            
            try:
                cursor = conexao.cursor()
                
                # Constrói a query dinamicamente - REMOVIDO atualizado_em
                set_clause = ", ".join([f"{campo} = %s" for campo in campos_para_atualizar.keys()])
                valores = list(campos_para_atualizar.values())
                valores.append(professor_id)
                
                # REMOVIDO: , atualizado_em = NOW()
                query = f"UPDATE usuarios SET {set_clause} WHERE id = %s"
                
                cursor.execute(query, valores)
                conexao.commit()
                
                # Atualiza a sessão se o email mudou
                if 'email' in campos_para_atualizar:
                    # Busca o nome completo atualizado
                    cursor.execute("SELECT nome_completo FROM usuarios WHERE id = %s", (professor_id,))
                    resultado = cursor.fetchone()
                    if resultado:
                        session['usuario'] = resultado[0]
                
                # Registra a atividade
                registrar_atividade(professor_id, 'professor', 'perfil_editado', 
                                  f'Perfil atualizado - Campos: {", ".join(campos_para_atualizar.keys())}')
                
                return jsonify({
                    'sucesso': True,
                    'mensagem': 'Perfil atualizado com sucesso!',
                    'dados': dados
                })
                
            except mysql.connector.Error as e:
                conexao.rollback()
                print(f"Erro ao atualizar perfil: {e}")
                return jsonify({'sucesso': False, 'erro': f'Erro no banco de dados: {str(e)}'}), 500
            finally:
                if conexao.is_connected():
                    cursor.close()
                    conexao.close()
        else:
            return jsonify({'sucesso': False, 'erro': 'Nenhum dado válido para atualizar'}), 400
            
    except Exception as e:
        print(f"Erro geral ao editar perfil: {e}")
        return jsonify({'sucesso': False, 'erro': 'Erro interno do servidor'}), 500

@app.route('/perfil_professor/especializacoes', methods=['POST'])
@login_required
def atualizar_especializacoes():
    """Atualiza as especializações do professor"""
    if session.get('tipo') != 'professor':
        return jsonify({'sucesso': False, 'erro': 'Acesso não autorizado'}), 403
    
    try:
        dados = request.get_json()
        if not dados or 'especializacoes' not in dados:
            return jsonify({'sucesso': False, 'erro': 'Dados não recebidos'}), 400
        
        professor_id = session.get('id_professor')
        especializacoes = dados['especializacoes']
        
        # Converte lista para string separada por vírgulas
        especializacoes_str = ', '.join([esp.strip() for esp in especializacoes if esp.strip()])
        
        conexao = conectar()
        if not conexao:
            return jsonify({'sucesso': False, 'erro': 'Erro de conexão com o banco'}), 500
        
        try:
            cursor = conexao.cursor()
            # REMOVIDO: , atualizado_em = NOW()
            cursor.execute("UPDATE usuarios SET expecializacoes = %s WHERE id = %s", 
                         (especializacoes_str, professor_id))
            conexao.commit()
            
            registrar_atividade(professor_id, 'professor', 'especializacoes_atualizadas', 
                              f'Especializações atualizadas: {especializacoes_str}')
            
            return jsonify({
                'sucesso': True,
                'mensagem': 'Especializações atualizadas com sucesso!',
                'especializacoes': especializacoes
            })
            
        except mysql.connector.Error as e:
            conexao.rollback()
            print(f"Erro ao atualizar especializações: {e}")
            return jsonify({'sucesso': False, 'erro': 'Erro no banco de dados'}), 500
        finally:
            if conexao.is_connected():
                cursor.close()
                conexao.close()
                
    except Exception as e:
        print(f"Erro geral ao atualizar especializações: {e}")
        return jsonify({'sucesso': False, 'erro': 'Erro interno do servidor'}), 500

@app.route('/perfil_professor/alterar_senha', methods=['POST'])
@login_required
def alterar_senha_professor():
    """Altera a senha do professor"""
    if session.get('tipo') != 'professor':
        return jsonify({'sucesso': False, 'erro': 'Acesso não autorizado'}), 403
    
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({'sucesso': False, 'erro': 'Dados não recebidos'}), 400
        
        senha_atual = dados.get('senha_atual', '').strip()
        nova_senha = dados.get('nova_senha', '').strip()
        confirmar_senha = dados.get('confirmar_senha', '').strip()
        
        # Validações
        if not all([senha_atual, nova_senha, confirmar_senha]):
            return jsonify({'sucesso': False, 'erro': 'Todos os campos são obrigatórios'}), 400
        
        if nova_senha != confirmar_senha:
            return jsonify({'sucesso': False, 'erro': 'As senhas não coincidem'}), 400
        
        if len(nova_senha) < 6:
            return jsonify({'sucesso': False, 'erro': 'A nova senha deve ter pelo menos 6 caracteres'}), 400
        
        professor_id = session.get('id_professor')
        
        # Verifica senha atual
        conexao = conectar()
        if not conexao:
            return jsonify({'sucesso': False, 'erro': 'Erro de conexão com o banco'}), 500
        
        try:
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT senha FROM usuarios WHERE id = %s", (professor_id,))
            resultado = cursor.fetchone()
            
            if not resultado:
                return jsonify({'sucesso': False, 'erro': 'Usuário não encontrado'}), 404
            
            # Verifica senha atual (em produção, use hash!)
            if resultado['senha'] != senha_atual:
                return jsonify({'sucesso': False, 'erro': 'Senha atual incorreta'}), 401
            
            # Atualiza a senha - REMOVIDO: , atualizado_em = NOW()
            cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", 
                         (nova_senha, professor_id))
            conexao.commit()
            
            registrar_atividade(professor_id, 'professor', 'senha_alterada', 'Senha alterada com sucesso')
            
            return jsonify({
                'sucesso': True,
                'mensagem': 'Senha alterada com sucesso!'
            })
            
        except mysql.connector.Error as e:
            conexao.rollback()
            print(f"Erro ao alterar senha: {e}")
            return jsonify({'sucesso': False, 'erro': 'Erro no banco de dados'}), 500
        finally:
            if conexao.is_connected():
                cursor.close()
                conexao.close()
                
    except Exception as e:
        print(f"Erro geral ao alterar senha: {e}")
        return jsonify({'sucesso': False, 'erro': 'Erro interno do servidor'}), 500
    

app.run(debug=True)