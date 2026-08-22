import urllib.request
import sys

# Ensure stdout uses utf-8
sys.stdout.reconfigure(encoding='utf-8')

def test_html():
    try:
        response = urllib.request.urlopen('http://localhost:5000/')
        html = response.read().decode('utf-8')
        print(f"HTML Status: {response.status}, Size: {len(html)} bytes")
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return False

    elements_to_check = [
        'navRankingsBtn',
        'navSimulatorBtn',
        'navValueRadarBtn',
        'mobileNavRankingsBtn',
        'mobileNavSimulatorBtn',
        'mobileNavValueRadarBtn',
        'simulatorSection',
        'simFighter1',
        'simFighter2',
        'simWeightClass',
        'simResults',
        'simProb1',
        'simProb2',
        'simBarName1',
        'simBarProb1',
        'simProbBarFill1',
        'swapSimulatorFighters',
        'simValueBetBox',
        'betMarketSelect',
        'betStakeInput',
        'switchMainTab',
        'quickSimulate',
        'safe-area-pb',
        'viewport-fit=cover',
        'headerVersionTag',
        'mobileHeaderVersionTag',
        'versionModal',
        'versionTimelineList',
        'openVersionModal',
        'closeVersionModal',
        'subTabValueBetsBtn',
        'subTabCLVBtn',
        'clvControls',
        'clvTrackerContainer',
        'clvBoutsGrid',
        'switchRadarSubView',
        'fetchCLVTracker',
        'openCLVHistoryModal',
        'closeCLVHistoryModal',
        'simCampAdvantageBadge',
        'simCampTier1',
        'simCampTier2',
        'simCampName1',
        'simCampName2',
        'simCampCoach1',
        'simCampCoach2',
        'simCampSynergy1',
        'simCampSynergy2',
        'simCampBreakdown'
    ]

    all_passed = True
    for el in elements_to_check:
        cnt = html.count(el)
        if cnt == 0:
            print(f"[FAIL] Missing element: {el}")
            all_passed = False
        else:
            print(f"[PASS] Found: {el} ({cnt} occurrences)")

    print("\n--- DOM ID Uniqueness Check ---")
    unique_ids = [
        'id="simFighter1"',
        'id="simFighter2"',
        'id="simResults"',
        'id="simulatorSection"',
        'id="navSimulatorBtn"',
        'id="mobileNavRankingsBtn"',
        'id="mobileNavSimulatorBtn"',
        'id="mobileNavValueRadarBtn"',
        'id="simValueBetBox"',
        'id="betMarketSelect"'
    ]

    for uid in unique_ids:
        cnt = html.count(uid)
        print(f"{uid}: {cnt} occurrence(s)")
        if cnt != 1:
            print(f"[FAIL] Duplicate or missing ID: {uid}")
            all_passed = False

    return all_passed

if __name__ == '__main__':
    res = test_html()
    if res:
        print("\n>>> ALL FRONTEND DOM AND MOBILE NAVIGATION CHECKS PASSED WITH 100% SUCCESS! <<<")
        sys.exit(0)
    else:
        print("\n>>> Frontend checks failed! <<<")
        sys.exit(1)
