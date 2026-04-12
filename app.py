import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

# --- CONFIGURAÇÃO DO SISTEMA ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lh_erp_nicolas_2026_secure'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_lh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELOS DE BANCO DE DADOS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Faturamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10)) # 'pagar' ou 'receber'
    empresa_slug = db.Column(db.String(50))
    categoria = db.Column(db.String(100))
    valor = db.Column(db.Float)
    vencimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pendente')
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)

class Colaborador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_slug = db.Column(db.String(50))
    nome = db.Column(db.String(100))
    cpf = db.Column(db.String(14))
    tipo_contrato = db.Column(db.String(20)) # CLT ou PJ
    cargo = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Ativo')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTAS DE ACESSO ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('selecao'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cpf_form = request.form.get('cpf')
        password_form = request.form.get('password')
        
        # Busca exata pelo CPF formatado ou limpo
        user = User.query.filter_by(cpf=cpf_form).first()
        
        if user and user.password == password_form:
            login_user(user)
            return redirect(url_for('selecao'))
        
        flash('CPF ou Senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# --- SELEÇÃO E CONTEXTO ---

@app.route('/selecao')
@login_required
def selecao():
    return render_template('selecao.html', nome=current_user.name)

@app.route('/set_empresa/<empresa_id>')
@login_required
def set_empresa(empresa_id):
    empresas = {'leao': 'Leão Serviços', 'health': 'Health Max'}
    if empresa_id in empresas:
        session['empresa_ativa'] = empresas[empresa_id]
        session['empresa_slug'] = empresa_id
        return redirect(url_for('dashboard'))
    return redirect(url_for('selecao'))

# --- MÓDULOS OPERACIONAIS ---

@app.route('/dashboard')
@login_required
def dashboard():
    empresa = session.get('empresa_ativa', 'Grupo L&H')
    return render_template('dashboard.html', empresa=empresa)

@app.route('/faturamento') # Contas a Pagar
@login_required
def faturamento():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    # Filtra apenas o que é "Pagar" desta empresa
    contas = Faturamento.query.filter_by(empresa_slug=slug, tipo='pagar').all()
    return render_template('faturamento.html', empresa=empresa, lancamentos=contas)

@app.route('/receber') # Contas a Receber
@login_required
def receber():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    # Filtra apenas o que é "Receber" desta empresa
    entradas = Faturamento.query.filter_by(empresa_slug=slug, tipo='receber').all()
    return render_template('receber.html', empresa=empresa, lancamentos=entradas)

@app.route('/rh')
@login_required
def rh():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    equipe = Colaborador.query.filter_by(empresa_slug=slug).all()
    return render_template('rh.html', empresa=empresa, colaboradores=equipe)

@app.route('/contratos')
@login_required
def contratos():
    empresa = session.get('empresa_ativa')
    return render_template('contratos.html', empresa=empresa)

# --- INICIALIZAÇÃO ---

def setup_db():
    with app.app_context():
        db.create_all()
        # Usuário mestre do Nicolas
        nicolas_cpf = "000.000.000-00"
        if not User.query.filter_by(cpf=nicolas_cpf).first():
            db.session.add(User(
                name="Nicolas Silva",
                cpf=nicolas_cpf,
                password="123"
            ))
            db.session.commit()
            print(">>> ERP L&H: Banco de Dados e Usuário Mestre prontos.")

if __name__ == '__main__':
    setup_db()
    app.run(debug=True)