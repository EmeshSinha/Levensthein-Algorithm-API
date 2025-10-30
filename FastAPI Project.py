import rapidfuzz
from rapidfuzz import fuzz
import re
from fastapi import FastAPI
import os
import signal
from pydantic import BaseModel
from fastapi.responses import FileResponse
from libindic.soundex import Soundex


app = FastAPI()
instance = Soundex()
class matchRequest(BaseModel):
    string1: str
    string2: str

@app.get("/")
def what_it_do():
    return {
        "message": "Program to intelligently compare two strings and output the similarity percent between those two",
        "/match": "POST JSON -> 'string1': str, 'string2': str ",
        "/shutdown": "POST query to kill the procedure"
    }

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(r"./logo/doitc_logo.png")


def rapidfuzz_features(a: str, b: str):
    """Return a dict of similarity features from various RapidFuzz algorithms."""
    return {
        "token_sort": fuzz.token_sort_ratio(a, b),
        "token_set": fuzz.token_set_ratio(a, b),
        "WRatio": fuzz.WRatio(a, b),
        "dam-lev": rapidfuzz.distance.DamerauLevenshtein.normalized_similarity(a,b)*100,
        "jaro-wink": rapidfuzz.distance.JaroWinkler.normalized_similarity(a,b,prefix_weight=0.1)*100

    }

def meta_scorer_static(a: str, b: str):
    features = rapidfuzz_features(a, b)
    weights = {
        "token_sort": 0.05,
        "token_set": 0.05,
        "WRatio": 0.1,
        "dam-lev": 0.4,
        "jaro-wink":0.4
    }
    score = sum(features[k] * weights[k] for k in features)
    return score

def description(obj: dict):
    score = obj.get("Meta Score", 0)
    soundex = obj.get("soundex", 0)
    ratio = obj.get("Ratio", 0)
    damlev = obj.get("DamLev", 0)
    og = obj.get("OG Similarity", 0)
    weighted = obj.get("Weighted Similarity", 0)

    # Primary scoring interpretation
    if soundex != 0:
        if score >= 95:
            summary = "The strings are essentially identical."
        elif score >= 85:
            summary = "The strings show very strong similarity and are likely referring to the same entity."
        elif score >= 70:
            summary = "The strings are moderately similar with some variations, possibly the same entity."
        elif score >= 50:
            summary = "The strings show mild similarity and may be related, but it is not definitive."
        elif score >= 30:
            summary = "The similarity is low — they are likely different entities."
        else:
            summary = "The strings are highly dissimilar — almost certainly different entities."

        # Secondary modifiers
        extras = []

        if soundex == 1:
            extras.append("Names sound phonetically similar.")
        elif soundex == -1:
            extras.append("Strings sound phonetically dissimilar.")

        if abs(ratio - damlev) > 20:
            extras.append("Significant spelling/structural differences detected.")

        if og + 20 < score:
            extras.append("Normalization greatly improved similarity (case, extensions, company words, dates removed).")

        if weighted - score > 15:
            extras.append("Token order differences heavily affect matching.")

        if extras:
            summary += " " + " ".join(extras)
    elif soundex == 0:
        summary = "Both strings after cleaning are completely identical"

    return summary




@app.post("/match")
def match_files(request: matchRequest):
    file1 = request.string1
    file2 = request.string2
    original1 = file1
    original2 = file2
    og_similarity = rapidfuzz.fuzz.ratio(original2,original1)

    # lowercase 
    
    file1 = file1.lower()
    file2 = file2.lower()
    
    # Remove salutations
    
    salutations_pattern = r"^(dr\.|dr |mr\.|mr |ms\.|ms |mrs\.|mrs |miss |prof\.|major |mjr\.|retired |retd\.|shrimati |shri |smt\.|smt |gen\.|general |gen )\s*"
    file1 = re.sub(salutations_pattern, "", file1)
    file2 = re.sub(salutations_pattern, "", file2)

    # remove extensions
    
    format_pattern = r"\.(pdf|docx|doc|txt|xlsx|xls|pptx|ppt|note|csv|json)$"
    file1 = re.sub(format_pattern, "", file1, flags=re.IGNORECASE)
    file2 = re.sub(format_pattern, "", file2, flags=re.IGNORECASE)

    # Remove non-alphanumeric chars and non white space 
    file1 = re.sub(r'[^a-zA-Z0-9]+', ' ', file1)
    file2 = re.sub(r'[^a-zA-Z0-9]+', ' ', file2)
    # Date pattern
    pattern = re.compile(
        r'('
        r'(?:[0-3]\d[01]\d\d{4})|'   # DDMMYYYY
        r'(?:[01]\d[0-3]\d\d{4})|'   # MMDDYYYY
        r'(?:\d{4}[01]\d[0-3]\d)|'   # YYYYMMDD
        r'(?:[0-3]\d[01]\d\d{2})|'   # DDMMYY
        r'(?:[01]\d[0-3]\d\d{2})'    # MMDDYY
        r')'
    )
    company_pattern = r'\b(ltd|limited|pvt\s+ltd|private\s+limited|llc|inc|retd|retired|incorporated|corp|corporation|co|company)\b\.?'
    file1 = re.sub(company_pattern, '', file1)
    file2 = re.sub(company_pattern, '', file2)
    #soundex
    soundexinst = instance.compare(file1,file2) # 0 if same string, 1 if phonetically the same
    # Match and remove dates
    match1 = re.search(pattern, file1)
    match2 = re.search(pattern, file2)
    sub1 = re.sub(pattern, "", file1)
    sub2 = re.sub(pattern, "", file2)
    # Fuzzy similarity
    normalsim = rapidfuzz.fuzz.ratio(file1,file2)
    similarity = rapidfuzz.fuzz.WRatio(file1, file2)
    sim1 = rapidfuzz.fuzz.QRatio(file1, file2)
    sim2 = rapidfuzz.fuzz.WRatio(sub1, sub2)
    #meta scorer
    final_similarity = meta_scorer_static(file1,file2)
    #damlev
    damlev = rapidfuzz.distance.DamerauLevenshtein.normalized_similarity(file1,file2)*100
    #jarowink 
    jarowink = rapidfuzz.distance.JaroWinkler.normalized_similarity(file1,file2,prefix_weight=0.1)*100

    meta_scorer = final_similarity
    
    
    if soundexinst == -1:
        final_similarity = final_similarity - 3 
    elif soundexinst == 1 and final_similarity < 95:
        final_similarity +=5
    
    if (similarity - final_similarity) > 20 and (similarity - final_similarity) < 35:
        final_similarity = similarity -10

    elif similarity - final_similarity >=30:
        final_similarity = similarity

    if (match1 and match2):
    
        if(similarity < 85):
            similarity += 5
        elif sim2 - similarity > 10:
            similarity = sim2 - 5


        comparison = {
        "file1": file1, "file2": file2, "original file1": original1, "original file2":original2, "soundex": soundexinst, "Ratio": normalsim, "DamLev":damlev, "JaroWink":jarowink, "Weighted Similarity":similarity, "Quick Similarity":sim1, "Meta Score": meta_scorer, "OG Similarity":og_similarity
        }

        return {"Study":comparison,"Comparision Summary": summary, "Final Score":final_similarity}
    else:
        comparison = {
        "file1": file1, "file2": file2, "original file1": original1, "original file2":original2, "soundex": soundexinst, "Ratio": normalsim, "DamLev":damlev, "JaroWink":jarowink, "Weighted Similarity":similarity, "Quick Similarity":sim1, "Meta Score": meta_scorer, "OG Similarity":og_similarity
        }        
        summary = description(comparison)
        return {"Study":comparison,"Comparision Summary": summary, "Final Score":final_similarity}

@app.post("/shutdown")
async def shutdown():
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)
    return {"message": "Server shutting down..."}