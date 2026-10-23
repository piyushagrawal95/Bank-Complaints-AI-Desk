import nodemailer from "nodemailer";

export default async function handler(req, res) {
  // Enable CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (e) {}
  }

  const { to_email, subject, html, text } = body || {};
  if (!to_email) {
    return res.status(400).json({ error: "Missing to_email parameter" });
  }

  const smtpUser = process.env.SMTP_USER;
  const smtpPass = process.env.SMTP_PASSWORD;
  const smtpHost = process.env.SMTP_HOST || "smtp.gmail.com";
  const smtpPort = Number(process.env.SMTP_PORT || 465);

  if (!smtpUser || !smtpPass) {
    return res.status(500).json({ error: "SMTP credentials are not configured in environment variables." });
  }

  const transporter = nodemailer.createTransport({
    host: smtpHost,
    port: smtpPort,
    secure: smtpPort === 465,
    auth: {
      user: smtpUser,
      pass: smtpPass,
    },
  });

  try {
    const info = await transporter.sendMail({
      from: `"Bank Complaint AI Desk" <${smtpUser}>`,
      to: to_email,
      subject: subject || "Confirm Your Account - Bank Complaint AI Desk",
      text: text || "",
      html: html || "",
    });
    console.log(`Email successfully delivered to ${to_email}:`, info.messageId);
    return res.status(200).json({ success: true, messageId: info.messageId });
  } catch (error) {
    console.error("Nodemailer error:", error);
    return res.status(500).json({ error: error.message });
  }
}
