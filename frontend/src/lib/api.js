import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const MEDIA = `${BACKEND_URL}`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});
