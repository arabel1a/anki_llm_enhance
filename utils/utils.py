import os
import pandas as pd
import zipfile
import xmltodict

SETTINGS_NAMES_LIST = ["@fontSizePx", "@sides", "@fieldType"]
SYSTEMPROMPT = """
You will enhance the Anki cards. Try to be short and concrete. I'll tip you $200 if your cards will be high-quality.
We will communicate in CSV format. DO NOT send anything in another format. Check your format carefully. 
All fields are string fields and MUST ALWAYS BE placed in double quotes (").
Format example:
front_text,back_text_1,back_text_2
"front_text_example_1","back_text_1_example_1","back_text_2_example_1"
"front_text_example_2","back_text_1_example_2","back_text_2_example_2"
"front_text_example_3","back_text_1_example_3","back_text_2_example_3"
"front_text_example_4","back_text_1_example_4","back_text_2_example_4"
"""

USERPROMPT = """
I use this deck for learning English.
I fill it manually and a bit messy, and I want you to make them more accurate.
My deck has the following columns: Front(=word), and Back(=translation).

I want you to 
1. Normalize, remove prepositions, and fix missprints in the 'word' field.
2. Look up the meaning, transcription, synonyms (separated by "|"), and 2-3 usage B2-level examples (separated by "\\n"). If many options are available, select one that aligns well with my 'translation' field. All these fields are in English.
3. The 'word' can be in English or in Russian. If the 'word; is in English, 'translation' would be Russian and vice versa.
4. If the word (in specified meaning) is used with particular proposition, add it too.
I have an example for you:

Input: 
```csv
word,translation
fledgling,новичок
bound, ехать куда-то
снисходительный,condescending
```

Output:
```csv
word,translation,transcription,meaning,synonyms,example
"снисходительный","condescending","/ˌkɒndɪˈsɛndɪŋ/","having or showing an attitude of patronizing superiority","patronizing | disdainful | haughty","Her condescending tone made it clear she thought she was smarter than everyone else in the room.\nHe offered condescending advice, as if I didn’t already know how to handle the situation.\nThe manager's condescending remarks about the team's efforts only demotivated them further."
"fledgling","новичок, зеленый юнец","/ˈflɛdʒlɪŋ/","a person or organization that is immature, inexperienced, or underdeveloped","beginner | novice | newcomer","The fledgling startup is still finding its footing in the competitive tech industry.\nAs a fledgling artist, she’s just starting to gain recognition for her work.\nThe fledgling team showed promise but lacked the experience to secure a victory."
"bound for","направляться ","/baʊnd/","going to or intended for a particular place","head to | destined to","The train was bound for Paris when it unexpectedly stopped in-between stations.\nShe felt excitement over her adventure as she packed her bags and prepared to be bound for new horizons.\nWe're currently bound for the mountains, expectinf to reach there by evening."

```
Here is the deck:
---
```csv
{0}
```
"""


def parse_anki_xml(file):
    """
    Parse AnkiApp iOS file format.
    :param file: file name in the decks folder
    :return: (cards_data, card fields settings data)
    Cards data is a DataFrame with card fields as columns and card as rows.
    Card fields settings data is a DataFrame with field settings as columns and field names as rows.
    """
    compressed = zipfile.ZipFile(f"decks/{file}", "r")
    file = compressed.open(file.replace("zip", "xml"))
    stream = file.read().decode("utf-8")
    data = xmltodict.parse(stream)["deck"]
    name = data["@name"]

    # Field settings
    field_list = []
    fields = data["fields"]
    for field_type, fields_of_this_type in fields.items():
        for field in fields_of_this_type:
            field["@fieldType"] = field_type
            if "@fontSizePx" not in field:
                field["@fontSizePx"] = "18"
            field_list.append(field)
    settings_data = pd.DataFrame(
        index=SETTINGS_NAMES_LIST,
        data={
            field["@name"]: [field["@fontSizePx"], field["@sides"], field["@fieldType"]]
            for field in field_list
        },
    )

    # Cards data
    cards = data["cards"]
    cards = data["cards"]["card"]
    cards_for_db = []
    bad_cards = []
    for iid, card in enumerate(cards):
        card_dict = {"id": iid}
        for field_type, fields_of_this_type in card.items():
            for field in fields_of_this_type:
                try:
                    # todo is located here in non-textual card felds?
                    card_dict[field["@name"]] = field["#text"]
                except:
                    bad_cards.append(card)
                    continue
        cards_for_db.append(card_dict)
    cards_data = pd.DataFrame(cards_for_db).set_index("id")
    cards_data.to_csv(f"csv/{name}.csv")
    settings_data.to_csv(f"csv/{name}_settings.csv")
    return cards_data, settings_data


def save_anki_xml(
    output_file, deck_name: str, cards_data: pd.DataFrame, settings_data: pd.DataFrame
):
    """
    Save DataFrame to AnkiApp iOS file format.
    :param output_file: output file name
    :param deck: DataFrame with cards
    :param settings: DataFrame with card fields settings
    :param name: deck name
    """
    xml = f"<deck name='{deck_name}'>\n"

    # Fields display settings
    xml += "\t<fields>\n"
    for column in settings_data.columns:
        xml += (
            f"\t\t<text name='{column}'"
            f" sides='{settings_data[column].loc['@sides']}'"
            f" fontSizePx='{settings_data[column].loc['@fontSizePx']}'>"
            f"</text>\n"
        )
    xml += "</fields>\n"

    xml += "\t<cards>\n"
    for index, card in cards_data.iterrows():
        if index in SETTINGS_NAMES_LIST:
            continue
        xml += "\t\t<card>"
        for field, value in card.items():
            xml += f"<text name='{field}'>{value}</text>"
        xml += "</card>\n"
    xml += "\t</cards>\n"
    xml += "</deck>"

    # saving
    xml_filename = "tmp/" + deck_name + ".xml"
    with open(xml_filename, "w") as xml_file:
        xml_file.write(xml)

    zip_filename = "decks/" + output_file
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(xml_filename, arcname=os.path.basename(xml_filename))
    os.remove(xml_filename)
