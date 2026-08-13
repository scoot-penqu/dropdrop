name: Auto Scan Pokemon Drops

on:
  schedule:
    - cron: '*/15 * * * *' # Runs automatically every 15 minutes
  workflow_dispatch: # Allows manual trigger anytime from GitHub

# THIS IS THE FIX FOR EXIT CODE 128
permissions:
  contents: write 

jobs:
  scrape-and-update:
    runs-on: ubuntu-latest
    steps:
      # THIS IS THE FIX FOR THE NODE.JS WARNING (Updated to v4)
      - name: Check out repo
        uses: actions/checkout@v4

      # THIS IS THE FIX FOR THE NODE.JS WARNING (Updated to v5)
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
            python-version: '3.x'

      - name: Run Scraper Script
        run: python scraper.py

      - name: Commit and push updated data.json
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          git add data.json
          git commit -m "Auto-updated drop data [skip ci]" || exit 0
          git push
