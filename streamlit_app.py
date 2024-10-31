import openai
import streamlit as st
import hashlib
import requests

# API keys
openai.api_key = st.secrets["openai_key"]
spoonacular_api_key = st.secrets["spoonacular_api_key"]

# Initialize session state for user database if it doesn't exist
if "user_db" not in st.session_state:
    st.session_state["user_db"] = {}
if "api_usage" not in st.session_state:
    st.session_state["api_usage"] = 0  # Track Spoonacular API usage

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to register users
def register_user(email, password):
    hashed_password = hash_password(password)
    if email in st.session_state["user_db"]:
        st.error("An account with this email already exists.")
        return False
    st.session_state["user_db"][email] = {"password": hashed_password, "preferences": {}}
    st.success("Account created successfully!")
    return True

# Function to log in users
def login_user(email, password):
    hashed_password = hash_password(password)
    if email in st.session_state["user_db"]:
        stored_password = st.session_state["user_db"][email]["password"]
        if stored_password == hashed_password:
            st.success("Login successful!")
            st.session_state["logged_in_user"] = email
            st.session_state["page"] = "Recipe Finder"
            return True
        else:
            st.error("Invalid email or password.")
    else:
        st.error("Invalid email or password.")
    return False

# Function to save user preferences
def save_user_preferences(email, dietary_restrictions, cuisine, enhancements):
    st.session_state["user_db"][email]["preferences"] = {
        "dietary_restrictions": dietary_restrictions,
        "cuisine": cuisine,
        "enhancements": enhancements,
    }
    st.success("Preferences saved!")

# Function to get user preferences
def get_user_preferences(email):
    return st.session_state["user_db"][email].get("preferences", {})

# Helper functions for Spoonacular API integration with usage tracking and quota handling
def fetch_recipes(ingredients, dietary_restrictions="", cuisine="", max_calories=None, min_protein=None):
    # Check and warn if usage limit is near the quota (e.g., assuming 150 requests/day)
    if st.session_state["api_usage"] >= 150:
        st.error("API usage limit reached for today. Please try again tomorrow.")
        return []

    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": spoonacular_api_key,
        "includeIngredients": ingredients,
        "diet": dietary_restrictions.lower() if dietary_restrictions != "None" else "",
        "cuisine": cuisine,
        "number": 1,
        "instructionsRequired": True
    }
    if max_calories:
        params["maxCalories"] = max_calories
    if min_protein:
        params["minProtein"] = min_protein

    response = requests.get(url, params=params)
    data = response.json()

    # Update API usage counter
    st.session_state["api_usage"] += 1

    # Handle API errors, including quota exceedance
    if response.status_code != 200:
        if "message" in data:
            st.error(f"API Error: {data['message']}")
        else:
            st.error("An error occurred while fetching recipes. Please try again later.")
        return []
    
    # Process results as usual
    results = data.get("results", [])
    if results:
        return results

    # Broaden search if no results found
    st.warning(f"Could not find an exact match for '{ingredients}'. Searching for similar recipes...")
    params.pop("includeIngredients")
    response = requests.get(url, params=params)
    data = response.json()
    
    # Update usage again for broader search
    st.session_state["api_usage"] += 1
    return data.get("results", [])

# Function to get recipe details from Spoonacular
def get_recipe_details(recipe_id):
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params = {"apiKey": spoonacular_api_key}
    response = requests.get(url, params=params)
    st.session_state["api_usage"] += 1  # Increment usage
    return response.json()

# Function to generate multiple enhancements sequentially based on user preferences
def generate_multiple_tips(recipe_description, enhancements):
    tip = recipe_description
    for enhancement in enhancements:
        prompt = f"Here is a recipe description: {tip}. How can I make it {enhancement}?"
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful cooking assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        tip = response.choices[0].message.content.strip()
    return tip

# Function to display recipe information with optional enhancements
def display_recipes_with_enhancements(recipes, enhancements=[]):
    shopping_items = []
    for recipe in recipes:
        st.write(f"### {recipe['title']}")
        st.image(recipe["image"], width=300)
        
        details = get_recipe_details(recipe["id"])
        st.write(details["summary"], unsafe_allow_html=True)
        
        ingredients = details["extendedIngredients"]
        shopping_items.extend([f"{ingredient['name']} - {ingredient['amount']} {ingredient['unit']}" for ingredient in ingredients])
        
        if enhancements:
            tip = generate_multiple_tips(details["summary"], enhancements)
            st.write(f"**Enhanced Tips:** {tip}")
        
        st.write(f"[View Full Recipe](https://spoonacular.com/recipes/{recipe['title'].replace(' ', '-').lower()}-{recipe['id']})")

    if shopping_items:
        st.write("### Shopping List")
        shopping_list_text = "\n".join(shopping_items)
        st.text_area("Shopping List", shopping_list_text, height=200)
        st.download_button("Download Shopping List", shopping_list_text)

# Page navigation setup
if "page" not in st.session_state:
    st.session_state["page"] = "Login"

# Main Application Logic
if st.session_state["page"] == "Login":
    st.title("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        login_user(email, password)

    if st.button("Create a New Account"):
        st.session_state["page"] = "Register"

    if st.button("Continue as Guest"):
        st.session_state["logged_in_user"] = "Guest"
        st.session_state["page"] = "Recipe Finder"

elif st.session_state["page"] == "Register":
    st.title("Register")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Create Account"):
        if email and password:
            registration_success = register_user(email, password)
            if registration_success:
                st.session_state["page"] = "Login"
        else:
            st.error("Please enter both email and password.")

    if st.button("Back to Login"):
        st.session_state["page"] = "Login"

elif st.session_state["page"] == "Recipe Finder":
    st.title("Advanced Recipe Finder and Enhancer")

    # Load saved preferences if available and user is not a guest
    if "logged_in_user" in st.session_state and st.session_state["logged_in_user"] != "Guest":
        user_email = st.session_state["logged_in_user"]
        saved_preferences = get_user_preferences(user_email)
        
        # Set defaults based on saved preferences
        dietary_restrictions = st.selectbox("Dietary Restrictions", ["None", "Vegan", "Vegetarian", "Gluten Free", "Keto"], index=["None", "Vegan", "Vegetarian", "Gluten Free", "Keto"].index(saved_preferences.get("dietary_restrictions", "None")))
        cuisine = st.selectbox("Cuisine Type", ["Any", "Indian", "Italian", "Mexican", "Chinese", "American", "Mediterranean"], index=["Any", "Indian", "Italian", "Mexican", "Chinese", "American", "Mediterranean"].index(saved_preferences.get("cuisine", "Any")))
        enhancements = st.multiselect("Choose Enhancements", ["spicier", "vegan", "Mediterranean twist", "kid-friendly"], default=saved_preferences.get("enhancements", []))
    else:
        # Guest user default selections
        dietary_restrictions = st.selectbox("Dietary Restrictions", ["None", "Vegan", "Vegetarian", "Gluten Free", "Keto"])
        cuisine = st.selectbox("Cuisine Type", ["Any", "Indian", "Italian", "Mexican", "Chinese", "American", "Mediterranean"])
        enhancements = st.multiselect("Choose Enhancements", ["spicier", "vegan", "Mediterranean twist", "kid-friendly"])

    # User inputs
    ingredients = st.text_input("Enter ingredients (comma-separated)", placeholder="e.g., chicken, rice, tomato")

    # Nutritional goals
    st.sidebar.title("Set Nutritional Goals")
    max_calories = st.sidebar.number_input("Max Calories", min_value=0, step=50)
    min_protein = st.sidebar.number_input("Min Protein (grams)", min_value=0, step=5)

    # Button to fetch and display recipes or personalized recommendations
    if st.button("Find and Enhance Recipe"):
        if ingredients:
            recipes = fetch_recipes(ingredients, dietary_restrictions, cuisine, max_calories, min_protein)
            if recipes:
                display_recipes_with_enhancements(recipes, enhancements if enhancements else [])
                
                # Save preferences if user is logged in (not a guest)
                if "logged_in_user" in st.session_state and st.session_state["logged_in_user"] != "Guest":
                    save_user_preferences(user_email, dietary_restrictions, cuisine, enhancements)
        else:
            st.error("Please enter ingredients to search for recipes.")

    if st.button("Logout"):
        del st.session_state["logged_in_user"]
        st.session_state["page"] = "Login"
