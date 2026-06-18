import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
from tqdm import tqdm
import argparse

from models import EpisodeMeta


def _xpath(driver, *xpaths, timeout=5):
    for xpath in xpaths:
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return elem.text
        except Exception:
            continue
    return ""


def _get_date(driver) -> str:
    try:
        elem = driver.find_element(By.XPATH, "//time")
        dt = elem.get_attribute("datetime")
        if dt:
            return dt
    except Exception:
        pass
    return _xpath(
        driver,
        "//span[contains(@class,'date')]",
        "//div[contains(@class,'date')]",
    )


def fetch_episode_meta(driver) -> EpisodeMeta:
    title = _xpath(driver, "//h1[contains(@class,'title')]")

    podcast = _xpath(
        driver,
        "//a[contains(@class,'podcast')]//span",
        "//div[contains(@class,'podcast')]//span",
        "//span[contains(@class,'podcast')]",
    )

    shownotes = ""
    shownotes_xpaths = [
        "//div[contains(@class,'description')]",
        "//div[contains(@class,'shownotes')]",
        "//div[contains(@class,'notes')]",
        "//div[contains(@class,'content') and not(ancestor::header)]",
        "//article[contains(@class,'description')]",
        "//section[contains(@class,'description')]",
    ]
    for xp in shownotes_xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xp)
            for e in elems:
                t = e.text.strip()
                if len(t) > len(shownotes):
                    shownotes = t
        except Exception:
            continue

    published_at = _get_date(driver)

    hosts = []
    guests = []
    host_selectors = [
        "//div[contains(@class,'host')]//span",
        "//div[contains(@class,'author')]//span",
        "//div[contains(@class,'creator')]//span",
    ]
    for sel in host_selectors:
        try:
            elems = driver.find_elements(By.XPATH, sel)
            texts = [e.text.strip() for e in elems if e.text.strip()]
            if texts:
                hosts = texts
                break
        except Exception:
            continue

    return EpisodeMeta(
        title=title,
        podcast=podcast,
        hosts=hosts,
        guests=guests,
        published_at=published_at,
        shownotes=shownotes,
        source_url=driver.current_url,
    )


def fetch_audio_file(url, progress_callback=None):
    print(f"downloading {url}")
    start_time = time.time()
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )
    end_time = time.time()
    print(f"driver init time: {end_time - start_time} seconds")

    try:
        print("正在加载页面...")
        driver.get(url)
        end_time = time.time()
        print(f"page load time: {end_time - start_time} seconds")

        meta = fetch_episode_meta(driver)
        print("播客标题:", meta.title)

        audio_element = driver.find_element(By.TAG_NAME, "audio")
        audio_url = audio_element.get_attribute("src")
        if not audio_url:
            print("网页中未找到音频文件。")
            return

        response = requests.get(audio_url, stream=True, verify=False)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024

        os.makedirs("audio_files", exist_ok=True)
        safe_title = "".join(c for c in meta.title if c.isalnum() or c in " _-").strip()
        if not safe_title:
            safe_title = str(int(time.time()))
        audio_path = os.path.join("audio_files", f"{safe_title}-episode_audio.mp3")
        meta_path = os.path.join("audio_files", f"{safe_title}.meta.json")

        if total_size > 0:
            downloaded = 0
            with open(audio_path, 'wb') as audio_file:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    audio_file.write(data)
                    if progress_callback:
                        progress = (downloaded / total_size)
                        progress_callback(progress)

            print(f"音频文件已保存到 {audio_path}")
        else:
            with open(audio_path, 'wb') as audio_file:
                audio_file.write(response.content)
            print(f"音频文件已保存到 {audio_path}")

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "title": meta.title,
                "podcast": meta.podcast,
                "hosts": meta.hosts,
                "guests": meta.guests,
                "published_at": meta.published_at,
                "duration": meta.duration,
                "shownotes": meta.shownotes,
                "source_url": meta.source_url,
            }, f, ensure_ascii=False, indent=2)

        return audio_path, meta

    finally:
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下载小宇宙播客音频文件")
    parser.add_argument(
        "-u", "--url",
        type=str,
        help="播客页面 URL",
        required=True
    )
    args = parser.parse_args()
    fetch_audio_file(args.url)

