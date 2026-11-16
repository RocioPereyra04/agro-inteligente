# AGRO-INTELIGENTE (Prototype + Demo)

**AGRO-INTELIGENTE** is a web-based agricultural management tool designed to map, visualize, and analyze rural land parcels. It allows farmers, agronomists, and students to geolocate fields, delimit boundaries using satellite maps or Google Earth, preview crop and soil profiles, and explore simulated terrain data in an interactive 3D environment.

---

## ✨ What the Application Does

- **Parcel Geolocation & Mapping:** Uses your device's GPS and interactive satellite maps to locate and visualize agricultural plots.
- **Google Earth Integration (KML):** Lets you jump directly to your coordinates in Google Earth, import existing parcel polygons (`.kml`), and export newly mapped land boundaries as `.kml` files.
- **Crop & Soil Reference:** Displays visual profiles of crops and soil types using Wikipedia imagery—or custom offline field photos stored locally.
- **3D Interactive Demo:** Includes a built-in 3D simulation mode (`demo/`) populated with sample agricultural data so you can explore the full vision of the platform without losing your current work.

---

## 🚀 How to Run the Application (Step-by-Step)

Because this app uses GPS geolocation, interactive maps, and local modules, **you must run it through a local web server** (double-clicking `index.html` directly will block some features).

1. **Unzip the project:**
   - Right-click the `.zip` file and select **Extract All...** (do not run the files from inside the compressed folder).
2. **Open the terminal inside the extracted folder:**
   - **Windows:** Open the extracted folder, click on the address bar at the top, type `cmd` (or `powershell`), and press **Enter**.
   - **Mac / Linux:** Right-click inside the folder and select **New Terminal at Folder** (or open Terminal and use `cd path/to/folder`).
3. **Start the local server:**
   - Type the following command and press **Enter**:
     ```bash
     python -m http.server 8000
     ```
   - *(Note: If `python` is not recognized on Windows, try `py -m http.server 8000`. On Mac/Linux, try `python3 -m http.server 8000`.)*
   - Leave this terminal window open while using the app.
4. **Open in your browser:**
   - Open **Chrome** or **Firefox** and go to:
     👉 **http://localhost:8000/**
   - *(Internet connection is required to load the satellite map tiles.)*

### 🔧 Troubleshooting (If you cannot access the page)
- **"This site can't be reached" / Connection refused:** Make sure the terminal window from Step 3 is still open and didn't show an error.
- **Port 8000 is already in use:** Try starting the server on another port, e.g., `python -m http.server 8080`, and then open `http://localhost:8080/`.
- **Python is not installed:** Download Python from [python.org](https://www.python.org/downloads/) (check *"Add Python to PATH"* during installation) or use the **Live Server** extension in Visual Studio Code.

---

## 🧭 Top Navigation Buttons
- **Prototype:** Explains that this version represents our initial project proposal.
- **Demo:** Launches the 3D interactive demo (from the `demo/` folder) on top of the app with simulated data. Click **"Back to the prototype"** at any time to return without losing anything you entered.

---

## 🌍 Google Earth Workflow
- **Open in Google Earth:** Opens your current location directly in Google Earth.
- **Import KML:** Draw your land boundary in Google Earth, save it as a `.kml` file, and upload it via **"Import KML"**.
- **Export KML:** At the end of your session, click **"View my land in Google Earth (KML)"** to download your parcel as a `.kml` file.

---

## 📸 Crop & Soil Photos
- By default, crop and soil photos are loaded from **Wikipedia** (internet connection required).
- **Use your own photos (offline):** Place `.jpg` files inside the `fotos/` folder following the naming rules in `fotos/README.txt`. Local photos automatically take priority over Wikipedia images.
