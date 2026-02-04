import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.eloscrape import EloScrape
import asyncio

async def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    eloscraper = EloScrape(
        directory=DIRECTORY, 
        tabEloStorage=716533894, 
        tabEloStorageCell="A2", 
        sheetName="ngm stats", 
        mu=10, 
        sigma=3, 
        beta=3, 
        tau=0.5, 
        draw_probability=0.01
    )
    await eloscraper.eloscrape()

if __name__ == '__main__':
    asyncio.run(main())