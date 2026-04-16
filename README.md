<div align="center">
  <img src="https://raw.githubusercontent.com/RohithKumar086/EchoNet-Triage/main/assets/logo%20ECho%20net.png" width="150" height="150"/>
  
  <h1>EchoNet-Triage</h1>
  
  <p><b>An offline-first, near-ultrasonic mesh network for zero connectivity crisis triage.</b></p>


  <br/>

</div>

EchoNet-Triage is an offline-first, decentralized mobile communication protocol designed for rapid crisis response in the hospitality sector. When traditional cellular networks and local Wi-Fi infrastructure fail, [Repo Name] utilizes near-ultrasonic frequencies (18kHz–22kHz) to transmit localized, encrypted distress packets (SOS, medical needs, structural hazards) from device to device.

By treating mobile phones as acoustic network nodes, we create a resilient "gossip protocol" mesh that routes critical triage data to first responders without relying on external internet connectivity.

Core Architecture:

Acoustic DSP Engine: Custom Frequency-Shift Keying (FSK) codec for data-over-audio transmission.

Offline Mesh Logic: Localized device-to-device packet routing with TTL (Time-to-Live) deduplication.

Crisis Command Dashboard: Real-time WebSockets integration for spatial mapping when a node regains connectivity.

