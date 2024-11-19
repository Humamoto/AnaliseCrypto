import streamlit as st
import pandas as pd
import yfinance as yf
import time
import asyncio
import requests
from datetime import datetime
from telegram import Bot
import logging

# Configuração de logging mais detalhada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class CryptoMonitor:
    def __init__(self):
        self.crypto_list = [
            'BTC-USD', 'ETH-USD', 'ADA-USD', 'XRP-USD', 'DOGE-USD',
            'SOL-USD', 'DOT-USD', 'MATIC-USD', 'LINK-USD', 'UNI-USD',
            'AVAX-USD', 'ATOM-USD', 'LTC-USD', 'BCH-USD', 'XLM-USD',
            'ALGO-USD', 'BNB-USD', 'SHIB-USD', 'TRX-USD', 'ETC-USD'
        ]
        
        # Configurações do Telegram
        self.telegram_token = "7070443655:AAGt7DMk1fjWrMh3DxDKFDsRb6u50X20b2k"
        self.telegram_chat_id = "-1002406561096"
        self.last_alert_time = {}  # Para controlar frequência de alertas
        
        try:
            self.telegram_bot = Bot(token=self.telegram_token)
            asyncio.run(self.test_telegram_connection())
        except Exception as e:
            logger.error(f"Erro ao inicializar Telegram Bot: {e}")
            self.telegram_bot = None

    async def test_telegram_connection(self):
        """Testa a conexão com o Telegram"""
        try:
            bot_info = await self.telegram_bot.get_me()
            logger.info(f"Bot conectado: @{bot_info.username}")
            
            await self.telegram_bot.send_message(
                chat_id=self.telegram_chat_id,
                text="🤖 Bot de monitoramento iniciado!\n\n"
                     "Monitorando variações de preço em criptomoedas..."
            )
            logger.info("Mensagem de teste enviada com sucesso!")
        except Exception as e:
            logger.error(f"Erro na conexão com Telegram: {e}")
            raise

    def check_all_variations(self, threshold, interval):
        variations = []
        failed_downloads = []
        current_time = datetime.now()
        
        for symbol in self.crypto_list:
            try:
                # Evitar requisições muito frequentes para a mesma moeda
                if symbol in self.last_alert_time:
                    time_diff = (current_time - self.last_alert_time[symbol]).total_seconds()
                    if time_diff < 300:  # 5 minutos entre alertas da mesma moeda
                        continue

                data = yf.download(symbol, period='1d', interval=interval, progress=False)
                
                if not data.empty and len(data) > 1:
                    initial_price = float(data['Close'].iloc[0].iloc[0])
                    current_price = float(data['Close'].iloc[-1].iloc[0])
                    variation = ((current_price - initial_price) / initial_price) * 100
                    
                    if abs(variation) >= threshold:
                        variations.append({
                            'symbol': symbol,
                            'variation': variation,
                            'current_price': current_price,
                            'initial_price': initial_price,
                            'timestamp': current_time.strftime("%H:%M:%S"),
                            'start_time': data.index[0].strftime("%H:%M:%S"),
                            'end_time': data.index[-1].strftime("%H:%M:%S")
                        })
                        self.last_alert_time[symbol] = current_time
            
            except Exception as e:
                failed_downloads.append(symbol)
                logger.error(f"Erro ao processar {symbol}: {e}")
                continue
        
        self.failed_downloads = failed_downloads
        return variations

    async def send_telegram_alert(self, message):
        """Envia mensagem para o Telegram"""
        if self.telegram_bot:
            try:
                await self.telegram_bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
                return True
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem no Telegram: {e}")
                return False
        return False

def main():
    st.set_page_config(
        page_title="Crypto Monitor",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🚨 Monitor de Variações de Criptomoedas")
    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        variation_threshold = st.number_input(
            "Variação mínima para alerta (%)",
            min_value=0.1,
            max_value=100.0,
            value=5.0,
            step=0.1
        )
        
        time_intervals = {
            "1 minuto": "1m",
            "5 minutos": "5m",
            "15 minutos": "15m",
            "30 minutos": "30m",
            "1 hora": "1h"
        }
        
        selected_interval = st.selectbox(
            "Intervalo de verificação",
            list(time_intervals.keys())
        )
        
        use_telegram = st.checkbox("Ativar alertas no Telegram", value=True)
    
    if st.sidebar.button("▶️ Iniciar Monitoramento"):
        try:
            monitor = CryptoMonitor()
            placeholder = st.empty()
            
            st.markdown("### 📝 Histórico de Alertas")
            alerts_history = st.empty()
            alerts_list = []
            
            while True:
                with placeholder.container():
                    variations = monitor.check_all_variations(
                        variation_threshold,
                        time_intervals[selected_interval]
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "Total de Moedas Monitoradas",
                            len(monitor.crypto_list),
                            delta=None
                        )
                    with col2:
                        st.metric(
                            "Alertas Ativos",
                            len(variations),
                            delta=f"+{len(variations)}" if variations else None
                        )
                    
                    if hasattr(monitor, 'failed_downloads') and monitor.failed_downloads:
                        st.warning(f"⚠️ Moedas indisponíveis: {', '.join(monitor.failed_downloads)}")
                    
                    if variations:
                        df = pd.DataFrame(variations)
                        df = df[['symbol', 'variation', 'current_price', 'initial_price', 'timestamp', 'start_time', 'end_time']]
                        df.columns = ['Moeda', 'Variação (%)', 'Preço Atual', 'Preço Inicial', 'Hora', 'Início', 'Fim']
                        
                        df['Variação (%)'] = df['Variação (%)'].round(2).astype(str) + '%'
                        df['Preço Atual'] = df['Preço Atual'].apply(lambda x: f"${x:,.4f}")
                        df['Preço Inicial'] = df['Preço Inicial'].apply(lambda x: f"${x:,.4f}")
                        
                        st.markdown("### 📊 Variações Detectadas")
                        st.dataframe(
                            df,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        if use_telegram:
                            async def send_alerts():
                                for var in variations:
                                    message = (
                                        f"🚨 <b>Alerta de Variação!</b>\n\n"
                                        f"💰 Moeda: {var['symbol']}\n"
                                        f"📈 Variação: {var['variation']:.2f}%\n"
                                        f"💵 Preço Inicial: ${var['initial_price']:.4f}\n"
                                        f"💵 Preço Atual: ${var['current_price']:.4f}\n"
                                        f"⏰ Período: {var['start_time']} - {var['end_time']}\n"
                                        f"📊 Intervalo: {selected_interval}"
                                    )
                                    success = await monitor.send_telegram_alert(message)
                                    if success:
                                        alerts_list.append({
                                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                                            'message': message
                                        })
                                        
                                        if len(alerts_list) > 10:
                                            alerts_list.pop(0)
                            
                            asyncio.run(send_alerts())
                            
                            alerts_history.markdown("\n\n".join([
                                f"**{alert['timestamp']}**\n```\n{alert['message']}\n```"
                                for alert in reversed(alerts_list)
                            ]))
                    
                    time.sleep(60)
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Erro durante o monitoramento: {e}")
            logger.error(f"Erro durante o monitoramento: {e}")
            raise

if __name__ == "__main__":
    main()
