// Razorpay Checkout.js loader + credit-pack purchase flow.
// Feature-flagged: /api/payments/razorpay/config returns {enabled:false}
// until ops set RAZORPAY_KEY_ID/SECRET, which makes all buy-buttons show
// a friendly "coming soon" state.
import { api } from "@/lib/api";
import { toast } from "sonner";

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

let scriptPromise = null;
function loadCheckoutScript() {
  if (typeof window === "undefined") return Promise.reject(new Error("SSR"));
  if (window.Razorpay) return Promise.resolve(true);
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = CHECKOUT_SRC;
    s.async = true;
    s.onload = () => resolve(true);
    s.onerror = () => { scriptPromise = null; reject(new Error("Failed to load Razorpay Checkout")); };
    document.body.appendChild(s);
  });
  return scriptPromise;
}

// Public helper — opens the Razorpay checkout modal for the given pack_id
// (from CREDIT_PACKS). Returns a Promise that resolves { credits_granted }
// on success, or rejects on any failure.
export async function purchaseCreditPack({ packId, onSuccess } = {}) {
  if (!packId) throw new Error("packId is required");
  await loadCheckoutScript();
  const { data: order } = await api.post("/payments/razorpay/create-order", { pack_id: packId });
  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay({
      key: order.key_id,
      amount: order.amount,
      currency: order.currency,
      name: "AI Video Studio",
      description: `${order.pack.label} — ${order.pack.credits} credits`,
      order_id: order.order_id,
      prefill: order.prefill || {},
      theme: { color: "#4F46E5" },
      handler: async (rp) => {
        try {
          const { data: verified } = await api.post("/payments/razorpay/verify", {
            razorpay_order_id: rp.razorpay_order_id,
            razorpay_payment_id: rp.razorpay_payment_id,
            razorpay_signature: rp.razorpay_signature,
          });
          if (verified.status === "paid") {
            toast.success(`+${verified.credits_granted || order.pack.credits} credits added!`);
            if (typeof onSuccess === "function") onSuccess(verified);
            resolve(verified);
          } else {
            toast.error("Payment verification failed — please contact support.");
            reject(new Error("verify_failed"));
          }
        } catch (e) {
          toast.error(e?.response?.data?.detail || "Payment verification failed.");
          reject(e);
        }
      },
      modal: {
        ondismiss: () => reject(new Error("user_dismissed")),
      },
    });
    rzp.on("payment.failed", (resp) => {
      const err = resp?.error?.description || "Payment failed.";
      toast.error(err);
      reject(new Error(err));
    });
    rzp.open();
  });
}
