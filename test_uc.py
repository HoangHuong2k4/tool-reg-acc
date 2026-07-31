import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
import subprocess
import re

out = subprocess.check_output(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"]).decode()
match = re.search(r"Chrome (\d+\.\d+\.\d+\.\d+)", out)
if match:
    version = match.group(1)
    print(f"Detected Chrome version: {version}")
    driver_path = ChromeDriverManager(driver_version=version).install()
    print(f"Downloaded driver path: {driver_path}")
    driver = uc.Chrome(driver_executable_path=driver_path, headless=True)
    print("Successfully launched!")
    driver.quit()
