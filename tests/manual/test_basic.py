"""
Manual testing script
Kjør dette etter hver uke for å validere grunnfunksjoner
"""
import requests
import logging

# Setup logging for test script
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:5000"

def test_server_running():
    """Test at serveren svarer"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        logger.info(f"✅ Server running: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        logger.error("❌ Server not running!")
        return False
    except Exception as e:
        logger.error(f"❌ Server test failed: {e}")
        return False

def test_basic_routes():
    """Test grunnleggende routes"""
    routes = [
        ("/", "Home"),
        ("/auth/login", "Login"),
        ("/dashboard", "Dashboard"),
        ("/documents", "Documents"),
        ("/calendar", "Calendar"),
        ("/tasks", "Tasks")
    ]

    logger.info("Testing basic routes...")
    for route, name in routes:
        try:
            response = requests.get(f"{BASE_URL}{route}", allow_redirects=False, timeout=5)
            # 200 = OK, 302 = Redirect (forventet for auth-protected routes)
            if response.status_code in [200, 302]:
                logger.info(f"✅ {name} ({route}): {response.status_code}")
            else:
                logger.warning(f"⚠️ {name} ({route}): {response.status_code}")
        except Exception as e:
            logger.error(f"❌ {name} ({route}): {e}")

def test_static_files():
    """Test at static files laster"""
    static_files = [
        ("/static/css/style.css", "Main CSS"),
        ("/static/js/main.js", "Main JS"),
        ("/static/logo.png", "Logo")
    ]

    logger.info("Testing static files...")
    for file_path, name in static_files:
        try:
            response = requests.get(f"{BASE_URL}{file_path}", timeout=5)
            status = "✅" if response.status_code == 200 else "❌"
            logger.info(f"{status} {name}: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ {name}: {e}")

def test_api_health():
    """Test API health endpoint hvis den finnes"""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ API Health check: OK")
        else:
            logger.info("ℹ️ API Health endpoint not available yet")
    except:
        logger.info("ℹ️ API Health endpoint not available yet")

if __name__ == "__main__":
    print("🧪 Manual Testing Script")
    print("=" * 40)

    if test_server_running():
        test_basic_routes()
        test_static_files()
        test_api_health()
    else:
        print("❌ Cannot run tests - server is not running")
        print("Start server with: python run.py")

    logger.info("Testing complete!")