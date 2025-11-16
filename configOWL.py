import configparser
from flask import Flask, render_template_string, request, redirect, url_for, flash
import os # 👈 AJOUTÉ : Importation nécessaire pour exécuter la commande système

# --- Configuration (MAIN CHANGES HERE) ---
INI_FILE_PATH = "/home/owl/owl/config/DAY_SENSITIVITY_2.ini"

# Définition des clés à modifier dans une liste de dictionnaires.
CONFIG_KEYS = [
    {"section": "GreenOnGreen", "key": "confidence", "type": "number", "label": "Seuil de Confiance (0.0 à 1.0)"},
    {"section": "GreenOnGreen", "key": "model_path", "type": "text", "label": "Chemin du Modèle"},
    {"section": "System", "key": "actuation_duration", "type": "number", "label": "Durée d'Action (secondes)"},
    {"section": "System", "key": "delay", "type": "number", "label": "Délai de Réponse (secondes)"},
    {"section": "DataCollection", "key": "sample_images", "type": "text", "label": "Capture d'image (True ou False)"},
]

# Initialiser l'application Flask
app = Flask(__name__)
app.secret_key = 'une_cle_secrete_aleatoire'


# --- La page web principale (l'interface) ---
@app.route('/', methods=['GET', 'POST'])
def config_page():
    config = configparser.ConfigParser()
    config.read(INI_FILE_PATH)
    
    # Structure pour stocker les valeurs actuelles et les métadonnées pour le template
    config_data = []

    # === Si l'utilisateur a soumis le formulaire (POST) ===
    if request.method == 'POST':
        
        # Parcourir toutes les clés que nous voulons modifier
        for item in CONFIG_KEYS:
            section = item["section"]
            key = item["key"]
            
            # Le nom du champ HTML est une combinaison de la section et de la clé (ex: GreenOnGreen-confidence)
            form_key = f"{section}-{key}"
            
            # 1. Récupérer la nouvelle valeur depuis le formulaire
            new_value = request.form.get(form_key)
            
            if new_value is not None:
                # 2. Mettre à jour l'objet config
                if not config.has_section(section):
                    config.add_section(section)
                    
                config.set(section, key, new_value)
        
        # 3. Écrire les modifications dans le fichier .ini (après avoir tout mis à jour)
        try:
            with open(INI_FILE_PATH, 'w') as configfile:
                config.write(configfile)
                
            # Au lieu d'afficher le message de succès et de rediriger vers la page principale,
            # nous redirigeons vers la nouvelle route de redémarrage.
            flash("Succès ! Configuration sauvegardée. Redémarrage en cours...", 'success')
            return redirect(url_for('reboot_now')) # 👈 MODIFICATION CLÉ
            
        except Exception as e:
            flash(f"Erreur lors de l'écriture du fichier : {e}", 'error')
            # Si échec, on redirige vers la page d'édition pour afficher l'erreur
            return redirect(url_for('config_page'))


    # === Si l'utilisateur charge juste la page (GET) ===
    # (Le reste de la fonction GET reste inchangé)

    # 1. Lire les valeurs actuelles de toutes les clés
    for item in CONFIG_KEYS:
        section = item["section"]
        key = item["key"]
        
        current_value = ""
        try:
            current_value = config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            current_value = "" 

        # Ajouter l'information à la liste de données pour le template
        config_data.append({
            "section": section,
            "key": key,
            "form_name": f"{section}-{key}", # Nom unique pour le champ HTML
            "type": item["type"],
            "label": item["label"],
            "value": current_value
        })

    # === Le code HTML de votre interface (MISE À JOUR) ===

    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Configuration Owl</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f4f4f4; }
            .container { max-width: 600px; margin: auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
            h2 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; margin-bottom: 20px; }
            .form-group { margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; border-radius: 8px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; font-size: 0.9em; }
            .key-label { font-size: 1.1em; color: #007bff; }
            input[type="text"], input[type="number"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; transition: border-color 0.3s; }
            input:focus { border-color: #007bff; outline: none; }
            button { background: #007bff; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 1.1em; transition: background 0.3s; }
            button:hover { background: #0056b3; }
            .flash { padding: 10px; margin-bottom: 15px; border-radius: 6px; font-weight: bold; }
            .flash.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .flash.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Configuration de OWL</h2>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="flash {{ category }}">{{ message }}</div>
                {% endfor %}
              {% endif %}
            {% endwith %}

            <form method="POST">
                
                {% for item in config_data %}
                <div class="form-group">
                    <label for="{{ item.form_name }}">
                        <span class="key-label">{{ item.label }}</span>
                        <br>
                        ({{ item.section }} / {{ item.key }})
                    </label>
                    <input type="{{ item.type }}" 
                            id="{{ item.form_name }}" 
                            name="{{ item.form_name }}" 
                            value="{{ item.value }}" 
                            {% if item.type == 'number' %}step="any"{% endif %}
                            required>
                </div>
                {% endfor %}

                <button type="submit">Enregistrer et Redémarrer le Raspberry Pi</button> </form>
        </div>
    </body>
    </html>
    """
    
    # Rendre le HTML en lui passant la liste complète des données
    return render_template_string(HTML_TEMPLATE, config_data=config_data)


# 🟢 NOUVELLE ROUTE : Gère l'exécution de la commande de redémarrage
@app.route('/reboot_now')
def reboot_now():
    # Message à afficher pendant que la commande est lancée
    reboot_message = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <title>Redémarrage du Raspberry Pi</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; background: #2c3e50; color: white; }
            .message-box { padding: 30px; border-radius: 10px; background: #34495e; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
            h1 { color: #2ecc71; }
        </style>
    </head>
    <body>
        <div class="message-box">
            <h1>✅ Redémarrage Lancé</h1>
            <p>Le Raspberry Pi est en cours de redémarrage. La connexion sera perdue.</p>
            <p>Vous pourrez vous reconnecter d'ici 30 à 60 secondes.</p>
        </div>
    </body>
    </html>
    """
    
    # Exécution de la commande. Nécessite l'autorisation sudo NOPASSWD: /sbin/reboot
    try:
        os.system('sudo reboot')
        return reboot_message, 200
    except Exception as e:
        # En cas d'échec de l'exécution, affichez une erreur (cela indique souvent un problème de permissions sudo)
        return f"Échec de l'exécution du redémarrage : {e}. Vérifiez la configuration sudoers.", 500


# --- Démarrer le serveur ---
if __name__ == '__main__':
    # 'debug=False' est recommandé si vous utilisez le redémarrage, car le rechargement 
    # automatique du code (reloader) peut interferer avec la commande de redémarrage.
    app.run(debug=False, host='0.0.0.0', port=5000)
