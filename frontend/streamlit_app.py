import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Support Ticket Assistant", layout="centered")

def api_request(method: str, path: str, token=None, **kwargs):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{API_BASE}{path}", headers=headers, **kwargs)

def render_login_register():
    tab_login, tab_register = st.tabs(["Login", "Register"])
    with tab_login:
        with st.form("login"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Log in"):
                resp = api_request("POST", "/login", json={"email": email, "password": password})
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["token"] = data["access_token"]
                    st.session_state["email"] = data["user"]["email"]
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Login failed"))
    with tab_register:
        with st.form("register"):
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_password")
            if st.form_submit_button("Create account"):
                resp = api_request("POST", "/register", json={"email": email, "password": password})
                if resp.status_code == 201:
                    st.success("Account created. Please log in.")
                else:
                    st.error(resp.json().get("detail", "Registration failed"))

def render_new_decision():
    st.subheader("New Decision")
    with st.form("ticket"):
        message = st.text_area(
            "Describe your issue",
            help="E.g. 'My ₹3,500 order arrived damaged yesterday.'",
        )
        col1, col2 = st.columns(2)
        order_value = col1.number_input("Order value (₹)", min_value=0, value=0)
        days_delivery = col1.number_input("Days since delivery", min_value=0, value=0)
        days_dispatch = col2.number_input("Days since dispatch", min_value=0, value=0)
        product_type = col2.selectbox(
            "Product type", ["", "food", "non_food", "mixed", "unknown"]
        )
        col3, col4 = st.columns(2)
        opened_status = col3.selectbox(
            "Opened status", ["", "unopened", "opened", "unknown"]
        )
        order_status = col4.selectbox(
            "Order status", ["", "delivered", "dispatched", "processing", "unknown"]
        )
        submitted = st.form_submit_button("Submit ticket & get decision")

    if submitted:
        if not message.strip():
            st.warning("Please describe your issue.")
            return
        token = st.session_state["token"]
        payload = {"message": message}
        if order_value > 0:
            payload["order_value_inr"] = order_value
        if days_delivery > 0:
            payload["days_since_delivery"] = days_delivery
        if days_dispatch > 0:
            payload["days_since_dispatch"] = days_dispatch
        if product_type:
            payload["product_type"] = product_type
        if opened_status:
            payload["opened_status"] = opened_status
        if order_status:
            payload["order_status"] = order_status
        with st.spinner("Analyzing ticket..."):
            resp = api_request("POST", "/tickets", token=token, json=payload)
        if resp.status_code == 201:
            data = resp.json()
            st.success("Decision generated.")
            st.markdown(f"**{data['decision']['action']}** — confidence {data['decision']['confidence']:.0%}")
            st.write(data["decision"]["reason"])
            st.write("Sources:", ", ".join(data["decision"]["sources"]))
        else:
            st.error(resp.json().get("detail", "Failed to process ticket"))

def render_history():
    st.subheader("History")
    token = st.session_state["token"]
    resp = api_request("GET", "/tickets", token=token)
    if resp.status_code != 200:
        st.error("Could not load tickets.")
        return
    tickets = resp.json().get("tickets", [])
    if not tickets:
        st.info("No tickets yet.")
        return
    labels = {t["id"]: t["message"][:60] + ("..." if len(t["message"]) > 60 else "") for t in tickets}
    picked = st.selectbox("Select a ticket", list(labels), format_func=lambda tid: labels[tid])
    detail_resp = api_request("GET", f"/tickets/{picked}", token=token)
    if detail_resp.status_code == 200:
        detail = detail_resp.json()
        st.markdown(f"**Message:** {detail['message']}")
        st.caption(f"Submitted: {detail['created_at']}")
        if detail.get("decision"):
            d = detail["decision"]
            st.markdown(f"**Action:** {d['action']}")
            st.markdown(f"**Confidence:** {d['confidence']:.0%}")
            st.markdown(f"**Reason:** {d['reason']}")
            st.markdown(f"**Sources:** {', '.join(d['sources'])}")
        else:
            st.info("No decision for this ticket yet.")
    else:
        st.error("Could not load ticket detail.")

def main():
    st.title("Support Ticket Decision Assistant")

    if "token" not in st.session_state:
        render_login_register()
        return

    st.caption(f"Logged in as {st.session_state['email']}")
    page = st.sidebar.radio("Menu", ["New Decision", "History"])
    st.sidebar.button("Log out", on_click=lambda: [st.session_state.pop(k, None) for k in ("token", "email")])

    if page == "New Decision":
        render_new_decision()
    else:
        render_history()

if __name__ == "__main__":
    main()