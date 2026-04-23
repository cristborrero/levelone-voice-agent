# Prompting Voice Agents to Sound More Realistic

**Fuente:** [LiveKit Blog](https://livekit.com/blog/prompting-voice-agents-to-sound-more-realistic)  
**Autor:** Shayne Parmelee  
**Fecha:** 26 de febrero de 2026  
**Tiempo de lectura:** 5 minutos  

---

## Descripción General

Una de las preguntas más comunes entre los desarrolladores de agentes de voz es:

> *"¿Debería usar un modelo speech-to-speech (S2S) o quedarme con el enfoque en cascada (STT → LLM → TTS)?"*

Lo que realmente están preguntando es: **¿cómo hago que mi agente suene más humano?**

Un pipeline en cascada puede ser tan rápido como un agente S2S y es más confiable para tool calling. Pero el problema es que suena como "lenguaje escrito leído en voz alta". Esto sucede porque los LLMs son entrenados sobre grandes cantidades de texto y luego afinados para producir escritura gramaticalmente correcta. Eso es ideal para chatbots y correos, pero **no es así como los humanos hablan**.

El habla real está llena de:
- Palabras de relleno (*filler words*)
- Correcciones a mitad de oración
- Pequeñas risas y pausas suaves
- Oraciones que divagan

> **La solución:** tu system prompt necesita hacer dos cosas bien: **mostrar al modelo lo que significa** hablar naturalmente, y **reforzar los mismos comportamientos desde múltiples ángulos**.

---

## 1. Define el Habla Natural con Ejemplos Concretos

Los LLMs no internalizan bien los objetivos de estilo vagos. Instrucciones como "sé conversacional" o "sé breve y natural" generalmente no producen patrones de habla realistas.

### Ejemplo de prompt ineficaz

```
You are a customer support agent.
You are brief with your responses.
You use filler words like "uhs" and "ums".
Your goal is natural, super conversational spoken exchanges.
```

### Lo que debes hacer en cambio

Piensa en qué suena "humano" para tu industria o caso de uso:

- ¿Qué palabras usa frecuentemente tu agente?
- ¿Cuándo debería hacer una pausa?
- ¿Cuál es la personalidad de tu agente?

Escribe oraciones concretas que tu agente podría decir en una conversación real. Si tienes grabaciones de llamadas entre clientes y agentes humanos, busca patrones en el habla humana que quieras replicar.

### Comparación de versiones

| Versión Mala | Versión Natural |
|---|---|
| "I can definitely handle that for you." | "Yeah, um so, I can do that, no problem." |
| "Unfortunately I'm going to have to cancel your service." | "So... um so... we're unfortunately going to have to cancel." |

Una vez que tengas varios ejemplos sólidos, puedes expandirlos usando otro LLM para generar variaciones y luego agregar las mejores de vuelta a tu system prompt.

---

## 2. Diseña Disfluencias con Patrones de Pausa Estructurados

Las palabras de relleno solas no son suficientes. Lo que las hace reales es el **timing**. Cuando los humanos dicen "um", generalmente hacen una breve pausa, luego reanudan con un conector como "so". Los agentes suelen fallar aquí: dicen "um" y luego continúan a toda velocidad, lo que suena falso.

### Uso de SSML Tags

Si tu motor TTS soporta [SSML tags](https://www.w3.org/TR/speech-synthesis11/), puedes enseñarle al modelo a imitar el timing con etiquetas de pausa:

```xml
<!-- Mala versión -->
"I can definitely handle that for you."

<!-- Tu versión con SSML -->
"Yeah, um <break time="300ms"/> so <break time="300ms"/>, I can do that, <break time="300ms"/> no problem."
```

### Estrategia de Refuerzo Múltiple

Para que el modelo aplique consistentemente las pausas, refuerza la regla desde múltiples ángulos:

1. **Enuncia la regla explícitamente:**
   ```
   After every standalone "um", immediately insert <break time="300ms"/>.
   ```

2. **Muestra ejemplos:**
   ```
   Yeah, um <break time="300ms"/> so <break time="300ms"/>, sure I can do that.
   ```

3. **Reitera la regla en otra sección con más ejemplos.**

> ⚠️ **Advertencia:** Abusar de las etiquetas de pausa en los ejemplos puede generar pausas en cada oración. Experimenta y ajusta según tu caso.

---

## 3. Usa Etiquetas de Emoción como Restricciones, No como Decoraciones

Los controles de emoción funcionan mejor como **guardarraíles**. Los humanos no alternan entre múltiples emociones en una sola oración. Si tu agente pasa de emocionado a divertido a triste a enojado en un turno, sonará muy inestable.

### Recomendaciones Clave

- Las etiquetas "calm"-adjacentes (como `peaceful`) tienden a sonar más humanas que las "grandes" emociones (como `excited`).
- Establece una línea base de calma y luego define escenarios específicos donde emociones más fuertes o risas tienen sentido.

### Ejemplos de Uso de Etiquetas

```xml
<!-- Baseline tranquilo -->
<emotion name="peaceful"/> Ya, okay so I can help with that.

<!-- Respuesta de alta energía (usar con moderación) -->
<emotion name="happy"/> Yeah <break time="300ms"/>, I totally get that.

<!-- Amabilidad a través de calma -->
<emotion name="peaceful"/> [laughter] Okay that is really funny.

<!-- Momento triste con pausas -->
<emotion name="sad"/> Yeah... um <break time="300ms"/> so... I'm really sorry about that.

<!-- Narrar una búsqueda en voz alta -->
Hmm, let me just check that <break time="500ms"/>. Ooone second here, <break time="300ms"/> Just looking at it for you.
```

> 💡 **Tip:** Puedes usar el tag `[laughter]` para que el agente ría. Úsalo libremente cuando sea apropiado: si el agente está feliz, probablemente debería reírse en algún momento.

---

## 4. Define la Personalidad como Comportamientos Auditivos, No Como Adjetivos

"Amigable y servicial" es el modo predeterminado de la mayoría de los LLMs. Para que el agente suene realista, necesitas rasgos de personalidad que se **mapeen a patrones de habla observables** — cosas que el modelo puede literalmente producir como output.

### Ejemplo de Prompt de Personalidad

```
You carry a steady, positive energy without being syrupy about it.
There is a chill confidence underneath everything.
Your default gear is relaxed enthusiasm.

Break grammar rules. Start sentences with "And," "But," or "So."
Break grammar rules in the common ways that people break grammar rules.
Use "like" often.

Loop back without referring to the specific subject when you need to go back.
Example: "About that other thing you mentioned"

Pauses are fine; when you fill them, use "ya" <break time="300ms"/>,
or "so yeah", or "anyway".

Whenever you say "um" then a <break/>, pick up again with "so" after the pause.

If confused or you think you misheard something:
"Sorry, I think I missed that, what did you say?"

When the customer says goodbye, wish them a good day!
```

Trata esta sección como un **checklist**: la mayoría de lo que incluyas debería escucharse en el audio.

---

## Resumen: Cómo Hacer que tu Agente Suene Menos Robótico

Si tu agente de voz suena robótico, revisa tu system prompt antes de culpar al modelo o al motor TTS. Aquí el checklist final:

- [ ] **Llena el prompt con ejemplos concretos** de oraciones que el agente debería decir
- [ ] **Sé específico sobre las disfluencias** (filler words con sus pausas y palabras de recuperación)
- [ ] **Empareja "um" con pausas y palabras de conexión** ("so" después de la pausa)
- [ ] **Refuerza la misma regla en múltiples secciones** del prompt
- [ ] **Define rasgos de personalidad como comportamientos observables**, no solo adjetivos
- [ ] **Repite las instrucciones más de lo que crees necesario** — el modelo casi siempre necesita más redundancia de la que esperas

---

## Recursos Adicionales

- [Documentación de LiveKit Agents](https://docs.livekit.io/)
- [Sesame Voice Demo](https://app.sesame.com/)
- [SSML W3C Specification](https://www.w3.org/TR/speech-synthesis11/)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)

---

*Documento generado a partir del artículo original de LiveKit Blog por Shayne Parmelee (26/02/2026).*
