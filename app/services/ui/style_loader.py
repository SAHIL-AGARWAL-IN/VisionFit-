import os
import streamlit as st
import streamlit.components.v1 as components


def load_css(file_path):
    if os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def inject_webrtc_styles():
    """Restyle the buttons inside the streamlit-webrtc iframe to match the app theme."""
    components.html(
        """
        <script>
        (function patchWebRTCStyles() {
            const css = `
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
                body { background: transparent !important; }
                .MuiPaper-root {
                    background: #1A1B1E !important;
                    color: #8A8D93 !important;
                    box-shadow: none !important;
                }
                .MuiButtonBase-root,
                .MuiButton-root {
                    font-family: 'Inter', system-ui, sans-serif !important;
                    text-transform: none !important;
                    letter-spacing: 0 !important;
                    font-weight: 600 !important;
                    border-radius: 999px !important;
                    box-shadow: none !important;
                    padding: 8px 20px !important;
                }
                .MuiButton-contained {
                    background: #FF4F12 !important;
                    color: #fff !important;
                }
                .MuiButton-contained:hover { background: #E8410A !important; }
                .MuiButton-text,
                .MuiButton-outlined {
                    color: #fff !important;
                    border: 1px solid rgba(255, 255, 255, 0.35) !important;
                }
                video { border-radius: 10px; background: #0F1012; }
            `;

            function injectIntoIframe(iframe) {
                try {
                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                    if (!doc || !doc.head) return;
                    if (doc.head.querySelector('#webrtc-custom-styles')) return;
                    const style = doc.createElement('style');
                    style.id = 'webrtc-custom-styles';
                    style.textContent = css;
                    doc.head.appendChild(style);
                } catch (e) {
                    console.warn('[patcher] could not inject:', e);
                }
            }

            function findAndPatch() {
                const iframes = window.parent.document.querySelectorAll('iframe');
                iframes.forEach(iframe => {
                    if (iframe.src && iframe.src.includes('webrtc')) {
                        if (iframe.contentDocument && iframe.contentDocument.readyState === 'complete') {
                            injectIntoIframe(iframe);
                        }
                        iframe.addEventListener('load', () => injectIntoIframe(iframe));
                    }
                });
            }

            findAndPatch();
            // The webrtc iframe can mount after this script runs.
            setTimeout(findAndPatch, 800);
            setTimeout(findAndPatch, 2500);
        })();
        </script>
        """,
        height=0,
    )
