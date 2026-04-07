from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Configurações do Sistema
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_financeiro.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Inicializa o Banco de Dados
db = SQLAlchemy(app)

# ==========================================
# MODELOS DE BANCO DE DADOS (As "Tabelas")
# ==========================================

class Faturamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50)) # Ex: Pago, Em aberto
    cidade = db.Column(db.String(100))
    servico = db.Column(db.String(200))
    empresa = db.Column(db.String(100))
    emissao_nota = db.Column(db.String(20)) # Usando string inicialmente para facilitar o input do HTML
    vencimento = db.Column(db.String(20))
    valor_nota = db.Column(db.Float)
    iss_retido = db.Column(db.Float)
    valor = db.Column(db.Float)
    porcentagem = db.Column(db.Float)
    valor_ir = db.Column(db.Float)
    valor_liquido = db.Column(db.Float)

class Despesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mes_referencia = db.Column(db.String(50)) # Ex: Janeiro, Fevereiro
    descricao = db.Column(db.String(200)) # Ex: Luz, Água, Aluguel
    vencimento = db.Column(db.String(20))
    valor = db.Column(db.Float)
    status = db.Column(db.String(50))
    caminho_comprovante = db.Column(db.String(200), nullable=True) 
    caminho_conta_luz = db.Column(db.String(200), nullable=True)
    caminho_nota_fiscal = db.Column(db.String(200), nullable=True)

# Cria o arquivo do banco de dados automaticamente na primeira vez
with app.app_context():
    db.create_all()

# ==========================================
# ROTAS DO SISTEMA (Navegação)
# ==========================================

@app.route('/')
def modulo_faturamento():
    # Busca todas as contas a receber no banco e envia para o HTML
    faturamentos = Faturamento.query.all()
    return render_template('index.html', faturamentos=faturamentos)

@app.route('/despesas')
def modulo_despesas():
    # Busca todas as contas a pagar no banco e envia para o HTML
    despesas = Despesa.query.all()
    return render_template('contas_pagar.html', despesas=despesas)

# Rota preparada para receber os uploads de comprovantes no futuro
@app.route('/upload_documento', methods=['POST'])
def upload_documento():
    if 'documento' in request.files:
        file = request.files['documento']
        if file.filename != '':
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            # Aqui depois colocaremos a lógica para atrelar o arquivo à despesa específica
    return redirect(url_for('modulo_despesas'))

if __name__ == '__main__':
    # Cria as pastas de upload caso não existam
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)