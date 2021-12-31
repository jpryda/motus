# About

[**Motus**](https://motus.pythonanywhere.com/) is a web app designed to help the avid calisthenics practitioner with workout sequencing. It allows you to delegate the programming of your workouts to a system that offers stochastic variety within high-level specified criteria. It finally allows you to push the workout to your own Notion workspace for more permanent logging.

**Flow**: [Input Notion DB](https://pear-knight-937.notion.site/9f2761e5a1c14987ae85f8e4d4a37f8e?v=8445b310230a40b7bd4ae2ca0d92bd8d)  \>  [**Motus**](https://motus.pythonanywhere.com/)  \>  personal Notion DB

You specify the following criteria in each "phase":

* Category {Push, Pull, Legs, Core, Movement}
* Equipment {Rings, Paralettes, None, High Bar, Parallel Bars, ...}
* Parent Exercise {Push-up, Dip, ...}
* N, the number of exercises to sample
* N Peak Intensity, the maximum number of "peak intensity" exercises of the N

# Features

* Rich curated selection of calisthenics exercises publicly available in [Notion](https://pear-knight-937.notion.site/9f2761e5a1c14987ae85f8e4d4a37f8e?v=8445b310230a40b7bd4ae2ca0d92bd8d); form cues, embedded videos guides, metadata including different intensities/whether the exercise is a "peak intensity" exercise.
* Export workouts to your own private Notion (using a lightning fast asynchronous implementation); copy to an Apple Note; or simply use as a web app in browser.
* Smartly orders your workout by 1) minimising the adjustment of ring heights and 2) placing peak intensity exercises toward the front.
* Manually reorder exercises via drag and drop.
* "Pin" specific exercises across generations that you know your body is craving.
* See the population size for a given combination of input criteria prior to sampling.

<img src="https://i.imgur.com/a5eNGTA.png" width="1000">
<img src="https://i.imgur.com/B6yhR2L.png" width="1000">

## Why Notion as the source?

* A UI that promotes editability and collaborative curation
* The ability to host **rich content**, form cues, and embed videos within pages
* The potential to clone others' DBs (ultimately to be able to plug in your own custom source)
* Support of semi-structured multi-select fields

## Why Notion for the output?

* Preserve rich content and form cues from the source
* Re-arrange the ordering of a workout easily
* Extend your personal Notion DB with additional logging columns
* Neatly store different workout permutations side-by-side

# FAQ

**Q: Why isn't the ordering of exercises preserved in the Notion output?**

A: Exercises are pushed *asynchronously* to Notion endpoints for a dramatic speed improvement. Rows can be sorted by sorting on the Order column in ascending order.

**Q: Can the ordering of columns be set for the Notion output?**

A: Currently Notion doesn't appear to allow you to specify the order of properties when you create a DB schema - it places the Title property first and fields are alphabetically sorted thereafter. This order can be adjusted in Notion.

**Q: Can the ordering of dropdown items be configured?**

A: The ordering is preserved from the Notion input DB source. These can be adjusted by those with edit access.

**Q: Why does the order of "pinned" exercises change on generation?**

A: Motus preserves the exercise but still tries to sort the workout by ring height and by peak intensity. It's possible/likely that the ordering of the pinned exercise will change.

# Tech

The app is written in Python and running on Flask. Asyncio and Httpx produce huge speed improvements since we avoid waiting on IO-blocking GET/PUSH requests as we pull and push 1) exercises (pages) 2) exercise content (child blocks) and 3) any synced blocks that require further dereferencing.

# Running the Flask App

```
git clone https://github.com/jpryda/motus.git app
```
Export the following environmental variables
```
NOTION_INTERNAL_SECRET (Internal Notion integration used to fetch the input Notion DB)
LOCAL_NOTION_CLIENT_ID
LOCAL_NOTION_CLIENT_SECRET
```
Launch the Flask app locally from the `app` folder
```
export FLASK_ENV=development; python -m flask run
```
In production set
```
PROD_NOTION_CLIENT_ID
PROD_NOTION_CLIENT_SECRET
```
