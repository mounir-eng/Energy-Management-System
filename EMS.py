import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

# Initialize session state variables
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame()
if 'battery_charge' not in st.session_state:
    st.session_state.battery_charge = 50  # Initial battery charge (%)

def generate_sample_data(hours=24):
    """Generate sample energy data for demonstration"""
    timestamps = [datetime.now() - timedelta(hours=x) for x in range(hours-1, -1, -1)]
    
    # Simulate varying PV generation (higher during midday)
    pv_gen = [max(0, 10 * np.sin(np.pi * (i / hours)) + random.uniform(-2, 2)) 
              for i in range(hours)]
    
    # Simulate building loads (higher during day)
    base_loads = {
        "Lighting": [random.uniform(5, 8) if 8 <= i <= 20 else random.uniform(2, 4) 
                     for i in range(hours)],
        "HVAC": [random.uniform(15, 30) if 9 <= i <= 17 else random.uniform(5, 15) 
                 for i in range(hours)],
        "Ventilation": [random.uniform(3, 6) for _ in range(hours)],
        "Gas_Thermal": [random.uniform(10, 20) if 6 <= i <= 22 else random.uniform(2, 8) 
                        for i in range(hours)]
    }
    
    # Calculate total load and grid interaction
    total_load = [sum(base_loads[load][i] for load in base_loads) for i in range(hours)]
    net_grid = [total_load[i] - pv_gen[i] for i in range(hours)]
    
    # Battery simulation (simplified)
    battery_flow = []
    battery_levels = [st.session_state.battery_charge]
    for i in range(hours):
        if net_grid[i] < 0:  # Excess PV -> charge battery
            charge = min(10, abs(net_grid[i]) * 0.8)  # 80% efficiency
            battery_flow.append(charge)
            battery_levels.append(min(100, battery_levels[-1] + charge))
        elif net_grid[i] > 0:  # Deficit -> discharge battery
            discharge = min(15, net_grid[i], battery_levels[-1] * 0.9)  # Max 90% discharge
            battery_flow.append(-discharge)
            battery_levels.append(max(0, battery_levels[-1] - discharge))
        else:
            battery_flow.append(0)
            battery_levels.append(battery_levels[-1])
    
    battery_levels = battery_levels[:-1]  # Remove last element
    
    return pd.DataFrame({
        'Timestamp': timestamps,
        'PV_Generation_kW': pv_gen,
        'Load_Lighting_kW': base_loads['Lighting'],
        'Load_HVAC_kW': base_loads['HVAC'],
        'Load_Ventilation_kW': base_loads['Ventilation'],
        'Load_Gas_Thermal_kW': base_loads['Gas_Thermal'],
        'Total_Load_kW': total_load,
        'Grid_Net_kW': net_grid,
        'Battery_Flow_kW': battery_flow,
        'Battery_Level_%': battery_levels
    })

def calculate_efficiency_metrics(df):
    """Calculate key performance indicators"""
    total_pv = df['PV_Generation_kW'].sum()
    total_consumed = df['Total_Load_kW'].sum()
    grid_import = df[df['Grid_Net_kW'] > 0]['Grid_Net_kW'].sum()
    grid_export = abs(df[df['Grid_Net_kW'] < 0]['Grid_Net_kW'].sum())
    battery_cycles = len([x for x in df['Battery_Flow_kW'] if x != 0])
    
    return {
        'Self_Sufficiency_%': (total_pv / total_consumed) * 100,
        'Grid_Import_kWh': grid_import,
        'Grid_Export_kWh': grid_export,
        'Battery_Cycles': battery_cycles,
        'Energy_Cost_Savings_$': (grid_import * 0.15) - (grid_export * 0.08)  # Simplified
    }

def main():
    st.set_page_config(page_title="Building Energy Management", layout="wide")
    st.title("🏢 Building Energy Management System")
    st.markdown("""
    Real-time monitoring and optimization of energy flows in buildings with PV, 
    battery storage, and mixed utility sources.
    """)
    
    # Generate or update data
    if st.button('🔄 Refresh Data'):
        new_data = generate_sample_data()
        st.session_state.data = new_data
        st.session_state.battery_charge = new_data.iloc[-1]['Battery_Level_%']
    elif st.session_state.data.empty:
        st.session_state.data = generate_sample_data()
    
    df = st.session_state.data
    
    # Display metrics
    metrics = calculate_efficiency_metrics(df)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Self-Sufficiency", f"{metrics['Self_Sufficiency_%']:.1f}%", "↗️ Optimizing")
    col2.metric("Grid Import", f"{metrics['Grid_Import_kWh']:.1f} kWh", "↘️ Reduced")
    col3.metric("Battery Cycles", metrics['Battery_Cycles'], "⚡ Stable")
    col4.metric("Cost Savings", f"${metrics['Energy_Cost_Savings_$']:.2f}", "💰 Efficient")
    
    # Energy Flow Visualization
    st.subheader("⚡ Energy Flow Diagram")
    flow_data = df.tail(1).iloc[0]
    fig_flow = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=["Utility Grid", "PV Panels", "Battery Storage", 
                   "Lighting", "HVAC", "Ventilation", "Gas Thermal"],
            color=["#FF7F0E", "#2CA02C", "#1F77B4", "#9467BD", "#D62728", "#8C564B", "#E377C2"]
        ),
        link=dict(
            source=[0, 1, 2, 0, 0, 0, 0],  # indices match labels above
            target=[3, 3, 3, 4, 5, 6, 2],
            value=[
                max(0, flow_data['Grid_Net_kW']),  # Grid to lighting
                flow_data['PV_Generation_kW'],     # PV to lighting
                max(0, flow_data['Battery_Flow_kW']), # Battery to lighting
                flow_data['Load_HVAC_kW'],         # Grid to HVAC
                flow_data['Load_Ventilation_kW'],   # Grid to Ventilation
                flow_data['Load_Gas_Thermal_kW'],   # Grid to Gas
                max(0, -flow_data['Battery_Flow_kW']) # Grid to Battery
            ]
        )
    ))
    st.plotly_chart(fig_flow, use_container_width=True)
    
    # Time Series Charts
    st.subheader("📈 Energy Monitoring Dashboard")
    fig_generation = px.line(df, x='Timestamp', y=['PV_Generation_kW', 'Total_Load_kW', 'Grid_Net_kW'],
                             title="Energy Generation vs Consumption")
    fig_generation.update_layout(hovermode="x unified")
    st.plotly_chart(fig_generation, use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        fig_battery = px.area(df, x='Timestamp', y='Battery_Level_%', 
                              title="Battery State of Charge")
        fig_battery.update_layout(yaxis=dict(range=[0, 100]))
        st.plotly_chart(fig_battery, use_container_width=True)
    
    with col2:
        fig_loads = px.bar(df.tail(6), x='Timestamp', 
                           y=['Load_Lighting_kW', 'Load_HVAC_kW', 'Load_Ventilation_kW', 'Load_Gas_Thermal_kW'],
                           title="Load Distribution (Last 6 Hours)")
        st.plotly_chart(fig_loads, use_container_width=True)
    
    # Optimization Recommendations
    st.subheader("🔧 Optimization Recommendations")
    recommendations = []
    peak_hour = df['Total_Load_kW'].idxmax()
    peak_time = df.loc[peak_hour, 'Timestamp'].strftime("%H:%M")
    
    if df['Grid_Net_kW'].mean() > 5:
        recommendations.append("- Shift high-consumption loads to midday when PV generation peaks")
    
    if df['Battery_Level_%'].min() < 20:
        recommendations.append("- Increase battery capacity to improve grid independence")
    
    if df['Load_HVAC_kW'].max() > 25:
        recommendations.append(f"- Peak HVAC demand at {peak_time} suggests need for thermal mass optimization")
    
    if df['Load_Gas_Thermal_kW'].mean() > 15:
        recommendations.append("- Consider heat pump integration for improved efficiency")
    
    if not recommendations:
        recommendations.append("✅ System operating efficiently within parameters")
    
    for rec in recommendations:
        st.info(rec)
    
    # Raw Data Table
    st.subheader("📊 Raw Data Table")
    st.dataframe(df.style.highlight_max(axis=0))

if __name__ == "__main__":
    main()
