import streamlit as st
import pymysql
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go

# Cargar variables de entorno
load_dotenv()

# Configuración de la conexión a la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'inventario')
}

# Configuración del servidor de correo
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': os.getenv('EMAIL_USER'),
    'password': os.getenv('EMAIL_PASSWORD')
}

# Lista de sectores
SECTORES = [
    'Comercio y servicios', 'Turismo', 'Industria', 'Parques industriales',
    'Economías regionales', 'Construcción', 'Mujeres empresarias', 'CAME Joven',
    'CAME Cultura', 'Eventos', 'Presidencia', 'Secretaria general', 'Hacienda',
    'Presupuestos', 'Capacitación', 'Rondas de negocios', 'Correspondencia',
    'Financiamiento', 'Recursos humanos', 'Dirección ejecutiva', 'Legales',
    'RSE', 'Base de datos', 'Comisión de asuntos tributarios', 'Comercio exterior',
    'CAME Sustentable', 'Fronteras e ilegalidad'
]

# Lista de provincias
PROVINCIAS = [
    'Buenos Aires', 'Ciudad Autónoma de Buenos Aires', 'Catamarca', 'Chaco',
    'Chubut', 'Córdoba', 'Corrientes', 'Entre Ríos', 'Formosa', 'Jujuy',
    'La Pampa', 'La Rioja', 'Mendoza', 'Misiones', 'Neuquén', 'Río Negro',
    'Salta', 'San Juan', 'San Luis', 'Santa Cruz', 'Santa Fe',
    'Santiago del Estero', 'Tierra del Fuego', 'Tucumán'
]

def init_connection():
    return pymysql(**DB_CONFIG)

def login():
    st.title("Sistema de gestión de inventario")
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        
    if not st.session_state.logged_in:
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Usuario")
        with col2:
            password = st.text_input("Contraseña", type="password")
            
        if st.button("Iniciar Sesión"):
            conn = init_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM usuarios 
                WHERE usuario = %s AND password = %s
            """, (username, password))
            user = cursor.fetchone()
            
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.experimental_rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
                
def enviar_correo(destinatario, asunto, mensaje):
    try:
        msg = MIMEText(mensaje)
        msg['Subject'] = asunto
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = destinatario
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error al enviar correo: {str(e)}")
        return False

def ver_stock():
    st.subheader("Stock Actual")
    conn = init_connection()
    df = pd.read_sql("SELECT * FROM productos", conn)
    st.dataframe(df)
    conn.close()

def realizar_pedido():
    st.subheader("Realizar Pedido")
    
    # Formulario principal
    with st.form("pedido_form"):
        fecha = st.date_input("Fecha", datetime.now())
        sector = st.selectbox("Sector", SECTORES)
        correo = st.text_input("Correo electrónico")
        tipo_entrega = st.radio("Tipo de entrega", ["Retirar", "Enviar"])
        
        if tipo_entrega == "Enviar":
            nombre_autoriza = st.text_input("Nombre y apellido de quien autoriza")
            direccion = st.text_input("Dirección")
            provincia = st.selectbox("Provincia", PROVINCIAS)
            codigo_postal = st.text_input("Código postal")
            nombre_receptor = st.text_input("Nombre y apellido del receptor")
            telefono = st.text_input("Teléfono")
        
        # Selección de materiales
        conn = init_connection()
        productos = pd.read_sql("SELECT producto FROM productos", conn)
        materiales = st.multiselect("Materiales", productos['producto'].tolist())
        cantidades = {}
        for material in materiales:
            cantidades[material] = st.number_input(f"Cantidad de {material}", min_value=1)
            
        fecha_entrega = st.date_input("Fecha de entrega estimada", 
                                     min_value=datetime.now().date() + timedelta(days=1))
        observaciones = st.text_area("Observaciones")
        
        submitted = st.form_submit_button("Enviar Pedido")
        
        if submitted:
            # Guardar pedido en la base de datos
            cursor = conn.cursor()
            detalle = ", ".join([f"{mat}: {cant}" for mat, cant in cantidades.items()])
            
            cursor.execute("""
                INSERT INTO pedidos (fecha_pedido, sector, quien_realiza_pedido, 
                detalle_pedido, envia_o_retira) 
                VALUES (%s, %s, %s, %s, %s)
            """, (fecha, sector, st.session_state.user['nombre'], detalle, tipo_entrega))
            
            conn.commit()
            
            # Enviar correo de confirmación
            mensaje_base = f"""
            Estimado/a {st.session_state.user['nombre']}:
            Se ha recibido con éxito su pedido de {detalle}.
            """
            
            if tipo_entrega == "Retirar":
                mensaje = mensaje_base + f"\nSu pedido podrá ser retirado el día {fecha + timedelta(days=1)} por el departamento de bases de datos."
            else:
                mensaje = mensaje_base + "\nSu pedido será cotizado. Una vez aprobado el presupuesto, se enviará a la dirección solicitada y será notificado por este medio."
            
            if enviar_correo(correo, "Recepción de solicitud", mensaje):
                st.success("Pedido registrado y correo enviado con éxito")
            
            conn.close()

def ver_historial():
    st.subheader("Historial de Pedidos")
    
    conn = init_connection()
    if st.session_state.user['tipo_usuario'] == 'admin':
        query = "SELECT * FROM pedidos ORDER BY fecha_pedido DESC"
    else:
        query = """
            SELECT * FROM pedidos 
            WHERE quien_realiza_pedido = %s 
            ORDER BY fecha_pedido DESC
        """
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, (st.session_state.user['nombre'],) if st.session_state.user['tipo_usuario'] != 'admin' else None)
    pedidos = cursor.fetchall()
    
    if st.session_state.user['tipo_usuario'] == 'admin':
        for pedido in pedidos:
            with st.expander(f"Pedido {pedido['id']} - {pedido['fecha_pedido']}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("Estado actual:", pedido['estado'])
                    nuevo_estado = st.selectbox(
                        "Actualizar estado",
                        ["En proceso", "Entregado", "Cancelado"],
                        key=f"estado_{pedido['id']}"
                    )
                with col2:
                    metodo_envio = st.selectbox(
                        "Método de envío",
                        ["Oca", "Motojet", "Retiró"],
                        key=f"envio_{pedido['id']}"
                    )
                with col3:
                    seguimiento = st.text_input(
                        "Número de seguimiento",
                        value=pedido['seguimiento'] or "",
                        key=f"seguimiento_{pedido['id']}"
                    )
                
                if st.button("Actualizar", key=f"actualizar_{pedido['id']}"):
                    cursor.execute("""
                        UPDATE pedidos 
                        SET estado = %s, metodo_envio = %s, seguimiento = %s
                        WHERE id = %s
                    """, (nuevo_estado, metodo_envio, seguimiento, pedido['id']))
                    conn.commit()
                    st.success("Pedido actualizado")
    else:
        for pedido in pedidos:
            st.write(f"Fecha: {pedido['fecha_pedido']}")
            st.write(f"Detalle: {pedido['detalle_pedido']}")
            st.write(f"Estado: {pedido['estado']}")
            st.markdown("---")
    
    conn.close()

def panel_control():
    if st.session_state.user['tipo_usuario'] != 'admin':
        st.error("Acceso no autorizado")
        return
        
    st.subheader("Panel de Control")
    
    conn = init_connection()
    cursor = conn.cursor()
    
    # Pedidos por sector
    cursor.execute("""
        SELECT sector, COUNT(*) as cantidad,
        SUM(CASE WHEN envia_o_retira = 'Enviar' THEN 1 ELSE 0 END) as envios,
        SUM(CASE WHEN envia_o_retira = 'Retirar' THEN 1 ELSE 0 END) as retiros
        FROM pedidos
        GROUP BY sector
    """)
    datos_sector = pd.DataFrame(cursor.fetchall(), 
                              columns=['Sector', 'Total', 'Envíos', 'Retiros'])
    
    # Mostrar tabla
    st.write("Pedidos por sector:")
    st.dataframe(datos_sector)
    
    # Gráfico de barras
    fig = px.bar(datos_sector, x='Sector', y=['Envíos', 'Retiros'],
                 title='Distribución de pedidos por sector',
                 barmode='group')
    st.plotly_chart(fig)
    
    # Métodos de envío
    cursor.execute("""
        SELECT metodo_envio, COUNT(*) as cantidad
        FROM pedidos
        WHERE metodo_envio IS NOT NULL
        GROUP BY metodo_envio
    """)
    datos_envio = pd.DataFrame(cursor.fetchall(),
                             columns=['Método', 'Cantidad'])
    
    # Gráfico circular
    fig = px.pie(datos_envio, values='Cantidad', names='Método',
                 title='Distribución de métodos de envío')
    st.plotly_chart(fig)
    
    conn.close()

def main():
    if not st.session_state.get('logged_in', False):
        login()
        return
        
    st.sidebar.title("Menú")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.experimental_rerun()
        
    opciones = {
        "Ver stock": ver_stock,
        "Realizar pedido": realizar_pedido,
        "Ver historial": ver_historial
    }
    
    if st.session_state.user['tipo_usuario'] == 'admin':
        opciones["Panel de control"] = panel_control
        
    opcion = st.sidebar.radio("Seleccione una opción:", list(opciones.keys()))
    opciones[opcion]()

if __name__ == "__main__":
    main()