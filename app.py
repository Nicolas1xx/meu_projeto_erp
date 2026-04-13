import os
import pandas as pd
from datetime import datetime
import math
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

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

class ContaReceber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_slug = db.Column(db.String(50))
    mes_referencia = db.Column(db.String(20))
    status = db.Column(db.String(50))
    cidade = db.Column(db.String(100))
    servico = db.Column(db.String(100))
    nf = db.Column(db.String(50))
    empresa_planilha = db.Column(db.String(100))
    emissao_nota = db.Column(db.String(50))
    vencimento = db.Column(db.String(50))
    valor_nota = db.Column(db.Float, default=0.0)
    iss_retido = db.Column(db.String(20))
    valor_iss = db.Column(db.Float, default=0.0)
    porcentagem = db.Column(db.String(20))
    valor_ir = db.Column(db.Float, default=0.0)
    valor_liquido = db.Column(db.Float, default=0.0)
    valor_recebido = db.Column(db.Float, default=0.0)
    diferenca = db.Column(db.Float, default=0.0)
    data_pg = db.Column(db.String(50))
    observacoes = db.Column(db.String(255))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- FUNÇÕES DE APOIO (MOTOR DE TRATAMENTO EXTREMO) ---
def limpar_moeda(val):
    """Transforma qualquer formato (R$, vírgula, texto) em Float seguro"""
    if pd.isna(val) or val is None or val == '': 
        return 0.0
    if isinstance(val, (int, float)): 
        return float(val)
    # Remove R$, espaços, pontos de milhar e troca vírgula por ponto
    v_str = str(val).upper().replace('R$', '').replace(' ', '').strip()
    v_str = v_str.replace('.', '').replace(',', '.')
    try:
        return float(v_str)
    except: 
        return 0.0

def formatar_data(d):
    """Limpa datas do Pandas/Excel para String Padrão"""
    if pd.isna(d) or d is None: return ""
    if isinstance(d, datetime): return d.strftime('%d/%m/%Y')
    d_str = str(d).strip()
    return d_str.split(' ')[0] if d_str else ""

# --- ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cpf_form = request.form.get('cpf')
        password_form = request.form.get('password')
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
    return redirect(url_for('login'))

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

@app.route('/dashboard')
@login_required
def dashboard():
    empresa = session.get('empresa_ativa', 'Grupo L&H')
    return render_template('dashboard.html', empresa=empresa)

# --- ROTAS DO MÓDULO FINANCEIRO (CONTAS A RECEBER) ---

@app.route('/receber')
@login_required
def receber():
    empresa = session.get('empresa_ativa')
    slug = session.get('empresa_slug')
    mes_filtro = request.args.get('mes', 'Todos')
    
    query = ContaReceber.query.filter_by(empresa_slug=slug)
    if mes_filtro != 'Todos':
        query = query.filter_by(mes_referencia=mes_filtro)
    
    # Ordenar por id (mais recentes primeiro) ou emissão, ajuste como preferir
    contas = query.order_by(ContaReceber.id.desc()).all()
    
    return render_template('receber.html', 
                           empresa=empresa, 
                           contas=contas,
                           mes_selecionado=mes_filtro)

@app.route('/upload_receber', methods=['POST'])
@login_required
def upload_receber():
    if 'excel_file' not in request.files: 
        return redirect(url_for('receber'))
    
    file = request.files['excel_file']
    if file.filename == '' or not file.filename.endswith(('.xlsx', '.xls')):
        flash('Nenhum arquivo selecionado ou formato inválido.', 'danger')
        return redirect(url_for('receber'))
    
    try:
        # Lendo a planilha com Pandas
        df = pd.read_excel(file)
        
        # 1. Padronização Absoluta de Colunas (tudo minúsculo e sem espaços sobrando)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # 2. Dicionário de Tolerância (Cobre 99% das variações de digitação humana)
        mapeamento = {
            'mes': 'mes_referencia', 'mês': 'mes_referencia', 'mes ref': 'mes_referencia',
            'status': 'status', 'cidade': 'cidade', 'servico': 'servico', 'serviço': 'servico',
            'nf': 'nf', 'nota fiscal': 'nf', 'nº nota': 'nf',
            'empresa': 'empresa_planilha', 'cliente': 'empresa_planilha', 'empresa/cliente': 'empresa_planilha',
            'emissao': 'emissao_nota', 'emissão': 'emissao_nota', 'data emissao': 'emissao_nota', 'emissão da nota': 'emissao_nota',
            'vencimento': 'vencimento', 'data vencimento': 'vencimento',
            'valor nota': 'valor_nota', 'bruto': 'valor_nota', 'valor bruto': 'valor_nota',
            'iss retido': 'iss_retido', 'iss retido?': 'iss_retido',
            'valor iss': 'valor_iss', 'iss': 'valor_iss',
            '%': 'porcentagem', 'porcentagem': 'porcentagem', 'taxa': 'porcentagem',
            'valor ir': 'valor_ir', 'ir': 'valor_ir',
            'valor liquido': 'valor_liquido', 'líquido': 'valor_liquido', 'valor líquido': 'valor_liquido',
            'valor recebido': 'valor_recebido', 'recebido': 'valor_recebido',
            'diferenca': 'diferenca', 'diferença': 'diferenca',
            'data pg': 'data_pg', 'pagamento': 'data_pg', 'data pagamento': 'data_pg',
            'obs': 'observacoes', 'observacoes': 'observacoes', 'observações': 'observacoes'
        }
        df.rename(columns=mapeamento, inplace=True)
        
        slug = session.get('empresa_slug')
        registros_salvos = 0

        for _, row in df.iterrows():
            # Pula a linha se não houver NF e nem valor
            if pd.isna(row.get('valor_nota')) and pd.isna(row.get('nf')):
                continue
                
            # Extração Financeira Blindada
            v_nota = limpar_moeda(row.get('valor_nota', 0))
            v_iss = limpar_moeda(row.get('valor_iss', 0))
            v_ir = limpar_moeda(row.get('valor_ir', 0))
            v_rec = limpar_moeda(row.get('valor_recebido', 0))
            
            # Cálculo Automático se a planilha vier incompleta
            v_liq = row.get('valor_liquido')
            v_liq = (v_nota - v_iss - v_ir) if pd.isna(v_liq) else limpar_moeda(v_liq)

            v_dif = row.get('diferenca')
            v_dif = (v_liq - v_rec) if pd.isna(v_dif) else limpar_moeda(v_dif)

            # Evita '.0' em NFs lidas como Float pelo Pandas
            nf_val = str(row.get('nf', '')).replace('.0', '').strip() if not pd.isna(row.get('nf')) else ''

            nova_conta = ContaReceber(
                empresa_slug=slug,
                mes_referencia=str(row.get('mes_referencia', 'Todos')).strip(),
                status=str(row.get('status', 'ABERTO')).upper().strip(),
                cidade=str(row.get('cidade', '')).strip(),
                servico=str(row.get('servico', '')).strip(),
                nf=nf_val,
                empresa_planilha=str(row.get('empresa_planilha', '')).strip(),
                emissao_nota=formatar_data(row.get('emissao_nota')),
                vencimento=formatar_data(row.get('vencimento')),
                valor_nota=v_nota,
                iss_retido=str(row.get('iss_retido', 'NÃO')).upper().strip(),
                valor_iss=v_iss,
                porcentagem=str(row.get('porcentagem', '')).strip(),
                valor_ir=v_ir,
                valor_liquido=v_liq,
                valor_recebido=v_rec,
                diferenca=v_dif,
                data_pg=formatar_data(row.get('data_pg')),
                observacoes=str(row.get('observacoes', '')).strip()
            )
            
            # Limpa qualquer campo que tenha virado string "nan"
            for col in nova_conta.__dict__:
                if str(getattr(nova_conta, col)).lower() == 'nan':
                    setattr(nova_conta, col, '')

            db.session.add(nova_conta)
            registros_salvos += 1
        
        db.session.commit()
        flash(f'{registros_salvos} registros sincronizados perfeitamente!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Falha ao processar o arquivo: {str(e)}', 'danger')
            
    return redirect(url_for('receber'))

@app.route('/adicionar_manual', methods=['POST'])
@login_required
def adicionar_manual():
    slug = session.get('empresa_slug')
    try:
        # Lógica de cálculo backend por segurança
        v_nota = limpar_moeda(request.form.get('valor_nota'))
        v_iss = limpar_moeda(request.form.get('valor_iss'))
        v_ir = limpar_moeda(request.form.get('valor_ir'))
        v_rec = limpar_moeda(request.form.get('valor_recebido'))
        
        v_liq = v_nota - v_iss - v_ir
        v_dif = v_liq - v_rec

        nova_conta = ContaReceber(
            empresa_slug=slug,
            mes_referencia=request.form.get('mes_referencia'),
            status=request.form.get('status', '').upper(),
            cidade=request.form.get('cidade'),
            servico=request.form.get('servico'),
            nf=request.form.get('nf'),
            empresa_planilha=request.form.get('empresa_planilha'),
            emissao_nota=request.form.get('emissao_nota'),
            vencimento=request.form.get('vencimento'),
            valor_nota=v_nota,
            iss_retido=request.form.get('iss_retido', '').upper(),
            valor_iss=v_iss,
            porcentagem=request.form.get('porcentagem'),
            valor_ir=v_ir,
            valor_liquido=v_liq,
            valor_recebido=v_rec,
            diferenca=v_dif,
            data_pg=request.form.get('data_pg'),
            observacoes=request.form.get('observacoes')
        )
        db.session.add(nova_conta)
        db.session.commit()
        flash('Novo lançamento registrado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro no lançamento: {e}', 'danger')
    return redirect(url_for('receber'))

@app.route('/deletar/<int:id>')
@login_required
def deletar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    db.session.delete(conta)
    db.session.commit()
    flash('Registro removido com sucesso!', 'info')
    return redirect(url_for('receber'))

@app.route('/limpar_receber')
@login_required
def limpar_receber():
    slug = session.get('empresa_slug')
    ContaReceber.query.filter_by(empresa_slug=slug).delete()
    db.session.commit()
    flash('Todos os dados foram apagados da base.', 'warning')
    return redirect(url_for('receber'))

# --- INICIALIZAÇÃO ---

def setup_db():
    with app.app_context():
        db.create_all()
        # Conta padrão do sistema
        if not User.query.filter_by(cpf="000.000.000-00").first():
            db.session.add(User(name="Nicolas Silva", cpf="000.000.000-00", password="123"))
            db.session.commit()

if __name__ == '__main__':
    setup_db()
    app.run(debug=True)