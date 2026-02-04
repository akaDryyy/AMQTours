import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.eloscrape import EloScrape
import asyncio

async def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    eloscraper = EloScrape(
        directory=DIRECTORY, 
        tabEloStorage=716533894, 
        tabEloStorageCell="A1", 
        sheetName="ngm stats", 
        mu=12, 
        sigma=1.75, 
        beta=7, 
        tau=0.09, 
        draw_probability=0.04
        )
    await eloscraper.eloscrape()

if __name__ == '__main__':
    asyncio.run(main())