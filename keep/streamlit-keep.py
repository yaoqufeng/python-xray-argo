import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StreamlitAppWaker:
    """针对 Streamlit 应用的自动唤醒工具"""
    
    APP_URL = os.environ.get("STREAMLIT_APP_URL", "")
    INITIAL_WAIT_TIME = 15  
    POST_CLICK_WAIT_TIME = 20  
    
    # 定位器常量
    TEST_ID_SELECTOR = "button[data-testid='wakeup-button-owner']"
    ROBUST_XPATH = "//button[contains(., 'Yes') and contains(., 'app back up')]"

    def __init__(self):
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        logger.info("⚙️ 正在设置 Chrome 驱动")
        chrome_options = Options()
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("✅ Chrome 驱动设置完成")
        except Exception as e:
            logger.error(f"❌ 驱动初始化失败: {e}")
            raise

    def find_and_click_button(self, context_description="当前上下文"):
        """综合尝试点击唤醒按钮"""
        try:
            # 1. 尝试显式等待并定位
            try:
                button = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.TEST_ID_SELECTOR))
                )
            except:
                button = WebDriverWait(self.driver, 4).until(
                    EC.presence_of_element_located((By.XPATH, self.ROBUST_XPATH))
                )

            # 2. 执行点击
            if button:
                try:
                    button.click()
                except:
                    # 如果元素被遮挡或不可直接点击，使用 JS 强制执行
                    self.driver.execute_script("arguments[0].click();", button)
                logger.info(f"✅ 在 {context_description} 成功触发点击")
                return True
        except:
            # 3. 最后的 JS 注入扫描方案 (针对 Shadow DOM 或动态加载)
            js_script = """
            var btn = document.querySelector("button[data-testid='wakeup-button-owner']");
            if(!btn) { 
                btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Yes')); 
            }
            if(btn) { btn.click(); return true; }
            return false;
            """
            if self.driver.execute_script(js_script):
                logger.info(f"✅ 通过 JS 强力扫描方案在 {context_description} 点击成功")
                return True
        
        return False

    def is_app_woken_up(self):
        """检查页面上是否还存在唤醒按钮"""
        self.driver.switch_to.default_content()
        
        def check_presence():
            # 同时检查主页面和嵌套 Iframe
            if self.driver.find_elements(By.CSS_SELECTOR, self.TEST_ID_SELECTOR): return False
            if self.driver.find_elements(By.XPATH, self.ROBUST_XPATH): return False
            
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for i in range(len(iframes)):
                try:
                    self.driver.switch_to.frame(i)
                    found = self.driver.find_elements(By.CSS_SELECTOR, self.TEST_ID_SELECTOR)
                    self.driver.switch_to.default_content()
                    if found: return False
                except:
                    self.driver.switch_to.default_content()
            return True

        # 给予 5 秒检测窗口期，确认按钮完全消失
        for _ in range(5):
            if check_presence(): return True
            time.sleep(1)
        return False

    def wakeup_app(self):
        if not self.APP_URL:
            raise Exception("⚠️ 环境变量 STREAMLIT_APP_URL 未配置")
        
        logger.info(f"👉 访问应用 URL: {self.APP_URL}")
        self.driver.get(self.APP_URL)
        time.sleep(self.INITIAL_WAIT_TIME)

        # 优先在主页面查找
        if self.find_and_click_button("主页面"):
            pass 
        else:
            # 深入探测 Iframe (Streamlit Cloud 常用嵌套结构)
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            found_in_iframe = False
            for i in range(len(iframes)):
                try:
                    self.driver.switch_to.frame(i)
                    if self.find_and_click_button(f"第 {i} 个 Iframe"):
                        found_in_iframe = True
                        break
                except:
                    pass
                finally:
                    self.driver.switch_to.default_content()
            
            if not found_in_iframe:
                # 检查是否因为应用已经醒着所以没找到按钮
                if self.is_app_woken_up():
                    return True, "✅ 应用已处于唤醒状态，无需重复操作"
                else:
                    raise Exception("❌ 在所有层级均未找到唤醒按钮")

        # 点击后的确认环节
        logger.info(f"⏳ 点击已完成，正在等待应用资源加载...")
        time.sleep(self.POST_CLICK_WAIT_TIME)

        if self.is_app_woken_up():
            return True, "✅ 应用唤醒流程执行成功"
        else:
            raise Exception("❌ 唤醒动作已执行，但检测到唤醒按钮依然存在")

    def run(self):
        try:
            success, msg = self.wakeup_app()
            return success, msg
        except Exception as e:
            return False, str(e)
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🧹 浏览器驱动已关闭")

if __name__ == "__main__":
    waker = StreamlitAppWaker()
    success, result = waker.run()
    logger.info(f"🚀 最终执行结果: {result}")
    # 退出码用于 GitHub Actions 状态反馈
    exit(0 if success else 1)
