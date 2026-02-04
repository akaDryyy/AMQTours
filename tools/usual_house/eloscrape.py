import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.eloscrape import EloScrape
import asyncio

async def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    eloscraper = EloScrape(
        directory=DIRECTORY, 
        tabEloStorage=716533894, 
        tabEloStorageCell="B5", 
        sheetName="ngm stats", 
        mu=12, 
        sigma=4, 
        beta=7, 
        tau=5, 
        draw_probability=0.04
        )
    await eloscraper.eloscrape(saveToSheet=False)

if __name__ == '__main__':
    asyncio.run(main())