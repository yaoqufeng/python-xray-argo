import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# 配置日志：使用更直观的格式
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class StreamlitAppWaker:
    """针对 Streamlit 应用的增强型自动唤醒工具"""
    
    APP_URL = os.environ.get("STREAMLIT_APP_URL", "")
    INITIAL_WAIT_TIME = 15  
    POST_CLICK_WAIT_TIME = 20  
    
    # 定位器
    TEST_ID_SELECTOR = "button[data-testid='wakeup-button-owner']"
    ROBUST_XPATH = "//button[contains(., 'Yes') and contains(., 'app back up')]"

    def __init__(self):
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        logger.info("⚙️ 正在初始化浏览器配置...")
        chrome_options = Options()
        chrome_options.page_load_strategy = 'eager' # 仅等待主 HTML 加载完成，不等待所有图片和追踪器
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("✅ 浏览器驱动就绪")
        except Exception as e:
            logger.error(f"❌ 驱动初始化失败: {str(e)}")
            raise

    def find_and_click_button(self, context="主页面"):
        """按钮点击逻辑"""
        logger.info(f"🔍 正在 [{context}] 搜索唤醒按钮...")
        
        button = None
        # 策略 1: Test-ID
        try:
            button = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.TEST_ID_SELECTOR))
            )
            strategy = "Test-ID"
        except:
            # 策略 2: XPath
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, self.ROBUST_XPATH))
                )
                strategy = "Robust-XPath"
            except:
                strategy = None

        if button:
            logger.info(f"🎯 命中按钮 (策略: {strategy})，准备执行点击...")
            try:
                button.click()
                logger.info(f"直接点击成功")
            except Exception:
                logger.warning(f"⚠️ 直接点击受阻，切换为 JavaScript 点击模式")
                self.driver.execute_script("arguments[0].click();", button)
            return True

        # 策略 3: JS 深度扫描
        logger.info(f"🧪 标准定位未果，尝试 JavaScript 深度扫描...")
        js_click_script = """
        var btn = document.querySelector("button[data-testid='wakeup-button-owner']");
        if(!btn) btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Yes'));
        if(btn) { btn.click(); return true; }
        return false;
        """
        if self.driver.execute_script(js_click_script):
            logger.info(f"⚡ JS 扫描成功触发点击")
            return True
        
        return False

    def check_app_status(self):
        """验证验证环节：检查唤醒按钮是否消失"""
        logger.info("🩺 正在验证唤醒结果（检查按钮是否依然存在）...")
        self.driver.switch_to.default_content()
        
        def is_gone():
            if self.driver.find_elements(By.CSS_SELECTOR, self.TEST_ID_SELECTOR): return False # 检查主页面
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe") # 检查 Iframe
            for i in range(len(iframes)):
                try:
                    self.driver.switch_to.frame(i)
                    found = self.driver.find_elements(By.CSS_SELECTOR, self.TEST_ID_SELECTOR)
                    self.driver.switch_to.default_content()
                    if found: return False
                except:
                    self.driver.switch_to.default_content()
            return True

        for attempt in range(1, 6):
            if is_gone():
                logger.info(f"✨ 验证通过：唤醒按钮已消失 (尝试第 {attempt} 次确认)")
                return True
            time.sleep(1)
        
        return False

    def wakeup_app(self):
        if not self.APP_URL:
            raise Exception("未检测到 STREAMLIT_APP_URL 环境变量")
        
        logger.info(f"🌐 正在访问目标地址: {self.APP_URL}")
        self.driver.get(self.APP_URL)
        
        logger.info(f"⏳ 等待页面初步渲染 ({self.INITIAL_WAIT_TIME}s)...")
        time.sleep(self.INITIAL_WAIT_TIME)

        # 尝试主页面
        if self.find_and_click_button("主页面"):
            logger.info("✅ 唤醒指令已发出")
        else:
            # 尝试 Iframe
            logger.info("📂 主页面未找到按钮，开始探测嵌套 Iframe...")
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"🔍 检测到 {len(iframes)} 个 iframe")
            
            clicked = False
            for i, frame in enumerate(iframes):
                try:
                    self.driver.switch_to.frame(frame)
                    if self.find_and_click_button(f"Iframe #{i}"):
                        clicked = True
                        break
                finally:
                    self.driver.switch_to.default_content()
            
            if not clicked:
                logger.info("🧐 搜索完毕：未找到任何唤醒按钮")
                if self.check_app_status():
                    return True, "应用已是唤醒状态，无需操作"
                else:
                    raise Exception("无法找到唤醒入口，且应用仍处于不可用状态")

        # 结果确认
        logger.info(f"🩺 正在最终验证唤醒结果...")
        if self.check_app_status():
            return True, "✅ 唤醒流程执行完毕，应用已恢复"
        else:
            error_msg = f"❌ 唤醒动作已执行，但验证失败：按钮依然存在"
            if os.getenv('GITHUB_ACTIONS'):
                print(f"::error::Waker failed to verify app status. Button still present.")
            raise Exception(error_msg)

    def run(self):
        try:
            success, msg = self.wakeup_app()
            logger.info(f"🚀 任务结束: {msg}")
            return success, msg
        except Exception as e:
            logger.error(f"💥 运行异常: {str(e)}")
            return False, str(e)
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🧹 浏览器会话已安全关闭")

if __name__ == "__main__":
    waker = StreamlitAppWaker()
    success, _ = waker.run()
    exit(0 if success else 1)
